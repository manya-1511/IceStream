"""
Day 2 tests: the data quality engine correctly classifies records.

These use small, hand-built dicts to exercise specific rules in isolation
(a normal unit-testing practice) — they are NOT presented anywhere as real
transactions. The actual data used by the running system always comes from
the real dataset (see streaming/reader.py, quality/engine.py).

Run with (from the project root):
    pytest tests/test_quality.py -v
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "quality"))

from engine import QualityEngine  # noqa: E402


def make_record(**overrides) -> dict:
    """A baseline valid record; tests override only the field(s) they care about."""
    base = {
        "invoice_no": "536365",
        "stock_code": "85123A",
        "description": "WHITE HANGING HEART T-LIGHT HOLDER",
        "quantity": 6,
        "invoice_date": datetime(2010, 12, 1, 8, 26, 0),
        "unit_price": 2.55,
        "customer_id": 17850,
        "country": "United Kingdom",
        "is_cancelled": False,
    }
    base.update(overrides)
    return base


def test_valid_record_passes():
    engine = QualityEngine()
    result = engine.check(make_record())
    assert result.valid is True
    assert result.reason is None
    assert result.rule is None


def test_null_required_field_fails_completeness():
    engine = QualityEngine()
    result = engine.check(make_record(invoice_no=None))
    assert result.valid is False
    assert result.rule == "rule_invoice_no_required"


def test_invalid_price_fails_validity():
    engine = QualityEngine()
    # Mirrors a real anomaly found in the actual dataset: a negative
    # unit_price on a non-cancellation invoice (see docs/QUALITY_RULES.md).
    result = engine.check(make_record(unit_price=-11.62, invoice_no="A563186", stock_code="B"))
    assert result.valid is False
    assert result.rule == "rule_unit_price_non_negative"


def test_invalid_quantity_fails_validity():
    engine = QualityEngine()
    # Negative quantity on a NON-cancellation invoice is invalid.
    result = engine.check(make_record(quantity=-6, is_cancelled=False))
    assert result.valid is False
    assert result.rule == "rule_quantity_sign_matches_cancellation"


def test_cancellation_with_negative_quantity_is_valid():
    """A real cancellation (negative qty + is_cancelled=True) must NOT be flagged."""
    engine = QualityEngine()
    result = engine.check(make_record(invoice_no="C536379", quantity=-1, is_cancelled=True))
    assert result.valid is True


def test_duplicate_line_item_fails_uniqueness():
    engine = QualityEngine()
    record = make_record()

    first = engine.check(record)
    assert first.valid is True
    engine.mark_seen(record)  # simulates the record actually being stored to valid_orders

    second = engine.check(dict(record))  # identical line item seen again
    assert second.valid is False
    assert second.rule == "rule_duplicate_line_item"


def test_check_alone_does_not_mark_a_record_as_seen():
    """
    Checking a record twice without ever storing it (mark_seen) must NOT
    trip the duplicate rule — this is exactly the Day 3 circuit-breaker
    scenario, where a record can be checked once while held, then
    re-checked again later during recovery.
    """
    engine = QualityEngine()
    record = make_record()

    first = engine.check(record)
    second = engine.check(dict(record))
    assert first.valid is True
    assert second.valid is True


def test_future_invoice_date_fails_validity():
    engine = QualityEngine()
    future = datetime.now() + timedelta(days=1)
    result = engine.check(make_record(invoice_date=future))
    assert result.valid is False
    assert result.rule == "rule_invoice_date_not_future"


def test_zero_quantity_is_invalid():
    engine = QualityEngine()
    result = engine.check(make_record(quantity=0))
    assert result.valid is False
    assert result.rule == "rule_quantity_sign_matches_cancellation"
