"""
Recovery.

    source dataset -> re-read affected records -> validate -> process again

When the circuit breaker has been QUARANTINED for a full window, it moves
to RECOVERING and this module runs: find every record that's sitting in
quarantine_orders *only* because the circuit was open (not because it
individually failed a quality rule — see streaming/db.py's
CIRCUIT_OPEN_RULE), re-read those exact records from the real dataset on
disk (the source of truth — we don't just trust our own quarantine copy),
run them through validate + the quality engine again, and promote the ones
that pass into valid_orders.

This is intentionally simple: a single pass, no retries-within-retries, no
external state. It's a realistic *local* demonstration of the self-healing
concept, not a production-grade recovery system — the pipeline is small
enough that "re-check everything that's pending" is cheap and correct.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "streaming"))
from reader import read_orders  # noqa: E402
from validator import validate_record  # noqa: E402
import db as streaming_db  # noqa: E402


@dataclass
class RecoveryResult:
    attempted: int
    recovered: int        # moved from quarantine_orders into valid_orders
    still_failing: int     # re-checked but genuinely still invalid
    success: bool          # True if nothing is still failing (circuit can close)


def attempt_recovery(engine, quality_engine, source: Path) -> RecoveryResult:
    circuit_open_rows = streaming_db.get_circuit_open_records(engine)

    if not circuit_open_rows:
        # Nothing was held purely due to the circuit being open (e.g. the
        # anomaly was a volume spike with no bad records) -> trivially healthy.
        return RecoveryResult(attempted=0, recovered=0, still_failing=0, success=True)

    # Natural key of each row we need to re-check.
    affected_keys = {
        (row["invoice_no"], row["stock_code"], row["invoice_date"]) for row in circuit_open_rows
    }
    # id lookup so we can delete/update the exact quarantine row afterwards
    row_id_by_key = {
        (row["invoice_no"], row["stock_code"], row["invoice_date"]): row["id"]
        for row in circuit_open_rows
    }

    recovered = 0
    still_failing = 0

    # Re-read the REAL dataset from disk and pick out exactly the affected
    # records — this is the "re-read affected records" step, sourced from
    # the same real data as everything else in this project.
    for raw_row in read_orders(source=source):
        key = (raw_row.get("invoice_no"), raw_row.get("stock_code"), raw_row.get("invoice_date"))
        if key not in affected_keys:
            continue

        row_id = row_id_by_key[key]
        record, parse_error = validate_record(raw_row)

        if parse_error:
            streaming_db.update_quarantine_reason(engine, row_id, "PARSE_ERROR", parse_error)
            still_failing += 1
            continue

        result = quality_engine.check(record)
        if result.valid:
            streaming_db.store_valid(engine, record)
            quality_engine.mark_seen(record)
            streaming_db.delete_quarantine_row(engine, row_id)
            recovered += 1
        else:
            # Genuinely fails independently of the circuit (e.g. it became
            # a duplicate of something stored since) — leave it in
            # quarantine, but relabel it with the real reason.
            streaming_db.update_quarantine_reason(engine, row_id, result.rule, result.reason)
            still_failing += 1

    attempted = recovered + still_failing
    return RecoveryResult(
        attempted=attempted,
        recovered=recovered,
        still_failing=still_failing,
        success=(still_failing == 0),
    )
