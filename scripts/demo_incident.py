"""
scripts/demo_incident.py — Day 3 controlled incident demonstration.

Runs one end-to-end scenario against the real dataset:

    normal stream (healthy)
        -> inject controlled NULL values into a required field on a
           fraction of real records
        -> error rate crosses the configured threshold
        -> an incident is created and the circuit breaker opens
           (QUARANTINED)
        -> further records are held in quarantine while the circuit is open
        -> normal (uncorrupted) records resume
        -> automatic recovery re-reads the held records from the real
           dataset ON DISK (not from the corrupted in-memory copies),
           re-validates them, and finds them genuinely valid
        -> circuit closes (RECOVERING -> HEALTHY), incident RESOLVED

Every record processed is a real row from data/processed/orders_clean.csv
(see docs/DATASET.md). The only synthetic element is the injected NULL
values — a controlled fault injected into real records, exactly as the
Day 3 spec asks for, to demonstrate the incident/recovery mechanism. The
source file on disk is never modified, which is exactly what lets recovery
re-read the correct original value afterwards.

Usage:
    python scripts/demo_incident.py
    python scripts/demo_incident.py --rate 50 --window-seconds 5
"""

from __future__ import annotations

import argparse
import copy
import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "streaming"))
from reader import read_orders, DEFAULT_SOURCE  # noqa: E402
import db as streaming_db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "quality"))
from engine import QualityEngine  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitoring"))
from pipeline import MonitoredPipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IceStream Day 3 controlled incident demo")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--rate", type=float, default=50.0, help="Records/sec (fast, for a quick demo)")
    parser.add_argument("--window-seconds", type=float, default=3.0, help="Short windows so the demo finishes quickly")
    parser.add_argument("--error-threshold", type=float, default=5.0)
    parser.add_argument("--healthy-count", type=int, default=60, help="Real records to stream normally first")
    parser.add_argument("--inject-count", type=int, default=60, help="Real records during the injection phase")
    parser.add_argument("--inject-fraction", type=float, default=0.4, help="Fraction of the injection phase to corrupt")
    parser.add_argument(
        "--recovery-count", type=int, default=90,
        help="Real, uncorrupted records to stream after injection, giving the circuit room to recover",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    total_needed = args.healthy_count + args.inject_count + args.recovery_count

    print(f"[DEMO] Loading {total_needed} real records from {args.source}")
    records = list(read_orders(source=args.source, limit=total_needed))
    if len(records) < total_needed:
        print(
            f"ERROR: dataset only has {len(records)} records available; reduce the phase counts.",
            file=sys.stderr,
        )
        sys.exit(1)

    healthy_phase = records[: args.healthy_count]
    inject_phase = records[args.healthy_count : args.healthy_count + args.inject_count]
    recovery_phase = records[args.healthy_count + args.inject_count : total_needed]

    # Controlled fault injection: corrupt an in-memory COPY only. The
    # original data/processed/orders_clean.csv on disk is never touched —
    # that's exactly what lets recovery re-read the correct value later.
    injected = []
    n_corrupted = 0
    cutoff = int(len(inject_phase) * args.inject_fraction)
    for i, row in enumerate(inject_phase):
        row = copy.deepcopy(row)
        if i < cutoff:
            row["unit_price"] = None  # NULL into a required field
            n_corrupted += 1
        injected.append(row)

    print(f"[DEMO] Phase 1: {len(healthy_phase)} real records, streamed normally")
    print(f"[DEMO] Phase 2: {len(injected)} real records, {n_corrupted} with unit_price forced to NULL")
    print(f"[DEMO] Phase 3: {len(recovery_phase)} real records, streamed normally (recovery should happen here)")

    engine = streaming_db.get_engine()
    streaming_db.truncate_pipeline_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE incidents RESTART IDENTITY"))
    print("[DATABASE] Truncated valid_orders, quarantine_orders, and incidents for a clean demo run\n")

    quality_engine = QualityEngine()
    pipeline = MonitoredPipeline(
        engine=engine,
        quality_engine=quality_engine,
        source=args.source,
        window_seconds=args.window_seconds,
        error_threshold=args.error_threshold,
    )

    interval = 1.0 / args.rate

    def stream_phase(name: str, rows: list[dict]) -> None:
        print(f"----- {name} -----")
        for row in rows:
            pipeline.handle_raw_row(row)
            time.sleep(interval)
        print()

    stream_phase("PHASE 1: NORMAL STREAM", healthy_phase)
    stream_phase("PHASE 2: INJECTING CONTROLLED NULLS", injected)
    stream_phase("PHASE 3: NORMAL STREAM RESUMES", recovery_phase)

    pipeline.finalize()

    print("===== DEMO SUMMARY =====")
    print(f"Total records streamed : {pipeline.total}")
    print(f"Valid records          : {pipeline.valid_count}")
    print(f"Invalid records        : {pipeline.invalid_count}")
    print(f"Held by open circuit   : {pipeline.held_by_circuit}")
    print(f"Final circuit state    : {pipeline.circuit.state.value}")

    print("\n----- Incidents -----")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT incident_id, type, severity, status, error_rate, description "
                "FROM incidents ORDER BY incident_id"
            )
        ).mappings().all()
    for r in rows:
        print(
            f"#{r['incident_id']} [{r['status']}] {r['type']}/{r['severity']} "
            f"error_rate={r['error_rate']}% - {r['description']}"
        )

    if pipeline.circuit.state.value == "HEALTHY" and rows and all(r["status"] == "RESOLVED" for r in rows):
        print("\n[DEMO] SUCCESS: an incident was detected, the circuit opened, and the pipeline recovered to HEALTHY.")
    else:
        print("\n[DEMO] Pipeline did not fully return to HEALTHY within this run — see incidents above.")
        print("[DEMO] Try increasing --recovery-count to give the circuit more clean records to recover on.")


if __name__ == "__main__":
    main()
