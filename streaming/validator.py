"""
The "validate" step of the pipeline:

    receive -> validate -> quality check -> store

This is deliberately separate from the quality engine. "Validate" here
means: can we even parse this row into the types our system expects
(numbers are numbers, dates are dates)? That's a different failure mode
from "the numbers are the wrong *business* value" (which is what
quality/rules.py checks).

In normal operation every row from orders_clean.csv already has correct
types (Day 1's preprocessing guaranteed that), so this step should always
succeed on our dataset. It exists so the pipeline is robust to a real
streaming source that might not be pre-cleaned, and so the two concerns
(parseable vs business-valid) aren't mixed into one function.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import pandas as pd


def _to_native(value):
    """Convert pandas/numpy scalar types to plain Python types (for JSON, logging, DB)."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):  # numpy scalar (int64, float64, bool_, ...)
        return value.item()
    return value


def validate_record(raw_row: dict) -> tuple[Optional[dict], Optional[str]]:
    """
    Returns (record, error):
      - (record, None) if the row parses successfully
      - (None, error_message) if it doesn't
    """
    try:
        record = {
            "invoice_no": _to_native(raw_row.get("invoice_no")),
            "stock_code": _to_native(raw_row.get("stock_code")),
            "description": _to_native(raw_row.get("description")),
            "quantity": _to_native(raw_row.get("quantity")),
            "invoice_date": _to_native(raw_row.get("invoice_date")),
            "unit_price": _to_native(raw_row.get("unit_price")),
            "customer_id": _to_native(raw_row.get("customer_id")),
            "country": _to_native(raw_row.get("country")),
            "is_cancelled": bool(_to_native(raw_row.get("is_cancelled"))),
        }

        # Type checks that must hold for the record to be usable downstream,
        # regardless of what the quality *rules* later decide about its values.
        if record["quantity"] is not None and not isinstance(record["quantity"], (int, float)):
            return None, f"quantity is not numeric: {record['quantity']!r}"
        if record["unit_price"] is not None and not isinstance(record["unit_price"], (int, float)):
            return None, f"unit_price is not numeric: {record['unit_price']!r}"
        if record["invoice_date"] is not None and not isinstance(record["invoice_date"], datetime):
            return None, f"invoice_date is not a valid timestamp: {record['invoice_date']!r}"

        if record["quantity"] is not None:
            record["quantity"] = int(record["quantity"])
        if record["customer_id"] is not None:
            record["customer_id"] = int(record["customer_id"])

        return record, None

    except Exception as exc:  # noqa: BLE001 - a parse step should never crash the stream
        return None, f"unexpected parse error: {exc}"


EMPTY_TYPED_RECORD = {
    "invoice_no": None,
    "stock_code": None,
    "description": None,
    "quantity": None,
    "invoice_date": None,
    "unit_price": None,
    "customer_id": None,
    "country": None,
    "is_cancelled": None,
}


def raw_to_jsonable(raw_row: dict) -> dict:
    """A best-effort, JSON-safe copy of a raw row, for the raw_record column."""
    safe = {}
    for key, value in raw_row.items():
        native = _to_native(value)
        if hasattr(native, "isoformat"):
            native = native.isoformat()
        safe[key] = native
    return safe
