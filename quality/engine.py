"""
The data quality engine.

QualityEngine.check(record) runs one record through, in order:
  1. Completeness rules
  2. Validity rules
  3. Uniqueness check (duplicate line-item detection)

...and stops at the first failure, so every record gets exactly one
(rule, reason) pair. This keeps quarantine_orders easy to read: one row,
one clear cause.

Every call to check() returns a QualityResult — this is the "every
processed record should produce: valid/invalid, reason, rule, timestamp"
requirement from the spec, as a plain Python object.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from rules import COMPLETENESS_RULES, VALIDITY_RULES


@dataclass
class QualityResult:
    valid: bool
    reason: Optional[str]
    rule: Optional[str]
    timestamp: datetime


class QualityEngine:
    def __init__(self) -> None:
        # Tracks line items we've already seen, for duplicate detection.
        # Key: (invoice_no, stock_code, quantity, unit_price, invoice_date)
        self._seen_keys: set[tuple] = set()

    def preload_seen_keys(self, keys: Iterable[tuple]) -> int:
        """
        Seed the duplicate-detection memory from records already stored in
        valid_orders (e.g. from a previous run), so restarting the stream
        doesn't forget what it already saw. Returns how many keys were loaded.
        """
        before = len(self._seen_keys)
        self._seen_keys.update(keys)
        return len(self._seen_keys) - before

    def mark_seen(self, record: dict) -> None:
        """
        Explicitly records a line item as seen, for future duplicate checks.

        Callers must call this themselves, exactly once, when a record is
        actually stored into valid_orders — check() itself does NOT do this
        automatically (see the note on check() below for why).
        """
        key = self._line_item_key(record)
        if key is not None:
            self._seen_keys.add(key)

    @staticmethod
    def _line_item_key(record: dict) -> Optional[tuple]:
        """
        The composite "natural key" of a line item. Returns None if any
        component is missing, since we can't meaningfully dedupe on a
        partial key (a completeness rule will already have rejected it).
        """
        fields = (
            record.get("invoice_no"),
            record.get("stock_code"),
            record.get("quantity"),
            record.get("unit_price"),
            record.get("invoice_date"),
        )
        if any(f is None for f in fields):
            return None
        return fields

    def check(self, record: dict) -> QualityResult:
        """
        Read-only: checking a record does NOT mark its key as seen.

        This matters once storage can be deferred (Day 3's circuit
        breaker holds otherwise-valid records in quarantine instead of
        storing them immediately). If check() marked a key as seen the
        moment it passed, a held record re-checked later during recovery
        would look like a duplicate of itself. Storing (streaming/db.py's
        store_valid) is always immediately followed by an explicit
        mark_seen() call by the caller — see streaming/run_stream.py and
        monitoring/pipeline.py.
        """
        now = datetime.now()

        for rule in COMPLETENESS_RULES:
            reason = rule(record)
            if reason:
                return QualityResult(False, reason, rule.__name__, now)

        for rule in VALIDITY_RULES:
            reason = rule(record)
            if reason:
                return QualityResult(False, reason, rule.__name__, now)

        # Uniqueness: only reachable once completeness + validity passed,
        # so we know the key fields are present and well-formed. This is a
        # read-only lookup — see mark_seen() for how keys get added.
        key = self._line_item_key(record)
        if key is not None and key in self._seen_keys:
            return QualityResult(
                False,
                f"duplicate line item already seen: invoice={key[0]} "
                f"stock_code={key[1]} quantity={key[2]} unit_price={key[3]} "
                f"invoice_date={key[4]}",
                "rule_duplicate_line_item",
                now,
            )

        return QualityResult(True, None, None, now)
