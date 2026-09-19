"""
Data quality rules.

Every rule is a plain function: (record: dict) -> str | None
  - returns None if the record PASSES the rule
  - returns a short human-readable reason string if it FAILS

`record` is a dict with the same fields as the `orders` table:
    invoice_no, stock_code, description, quantity, invoice_date,
    unit_price, customer_id, country, is_cancelled

These rules only cover fields that actually exist in the real Online
Retail II dataset (see docs/DATASET.md) — there is no rule here for, say,
"category" or "warehouse_id", because our dataset doesn't have those.

Two rules were adapted specifically to real patterns found in this dataset
(see docs/QUALITY_RULES.md for the full reasoning, with real examples):

  - quantity: the raw generic rule "quantity > 0" would incorrectly flag
    every legitimate cancellation (which has negative quantity by design —
    UCI's own documentation says an invoice starting with 'C' is a
    cancellation). So the rule is quantity-sign-must-match-cancellation-flag.
  - uniqueness: `invoice_no` is NOT a unique order ID in this dataset — one
    invoice legitimately has many rows (one per product). So "duplicate ID"
    is implemented as a duplicate *line item*: the same invoice + product +
    quantity + price + timestamp appearing twice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def _is_missing(value) -> bool:
    """True for None, NaN, or an empty/whitespace-only string."""
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN check without importing math/pandas here
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


# --- Completeness ---------------------------------------------------------

def rule_invoice_no_required(record: dict) -> Optional[str]:
    """The invoice number is our required order identifier."""
    if _is_missing(record.get("invoice_no")):
        return "invoice_no is missing (required identifier)"
    return None


def rule_unit_price_required(record: dict) -> Optional[str]:
    if _is_missing(record.get("unit_price")):
        return "unit_price is missing"
    return None


def rule_invoice_date_required(record: dict) -> Optional[str]:
    if _is_missing(record.get("invoice_date")):
        return "invoice_date is missing"
    return None


# --- Validity ---------------------------------------------------------

def rule_quantity_sign_matches_cancellation(record: dict) -> Optional[str]:
    """
    Real rule from the dataset (see docs/QUALITY_RULES.md):
      - is_cancelled == True  -> quantity must be negative
      - is_cancelled == False -> quantity must be positive
    Either way, quantity can never be exactly 0 in this dataset.
    """
    quantity = record.get("quantity")
    if _is_missing(quantity):
        return None  # handled by completeness-style checks elsewhere if needed

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return f"quantity is not a whole number: {record.get('quantity')!r}"

    if quantity == 0:
        return "quantity is 0 (no real order line has zero quantity)"

    is_cancelled = bool(record.get("is_cancelled"))
    if is_cancelled and quantity > 0:
        return f"quantity is positive ({quantity}) but invoice is flagged as a cancellation"
    if not is_cancelled and quantity < 0:
        return f"quantity is negative ({quantity}) on a non-cancellation invoice"

    return None


def rule_unit_price_non_negative(record: dict) -> Optional[str]:
    """
    unit_price == 0 is kept as valid (real promotional/free items exist in
    this dataset). unit_price < 0 is not a normal transaction — the real
    dataset contains a small number of these (bad-debt adjustment entries,
    invoice numbers starting with 'A') and they are exactly the kind of
    anomaly this platform exists to catch.
    """
    unit_price = record.get("unit_price")
    if _is_missing(unit_price):
        return None  # completeness rule already covers this

    try:
        unit_price = float(unit_price)
    except (TypeError, ValueError):
        return f"unit_price is not a number: {record.get('unit_price')!r}"

    if unit_price < 0:
        return f"unit_price is negative ({unit_price})"
    return None


def rule_invoice_date_not_future(record: dict) -> Optional[str]:
    invoice_date = record.get("invoice_date")
    if _is_missing(invoice_date):
        return None  # completeness rule already covers this

    if isinstance(invoice_date, str):
        try:
            invoice_date = datetime.fromisoformat(invoice_date)
        except ValueError:
            return f"invoice_date is not a valid timestamp: {invoice_date!r}"

    if invoice_date > datetime.now():
        return f"invoice_date is in the future: {invoice_date}"
    return None


# --- Uniqueness ---------------------------------------------------------
# Implemented in quality/engine.py (QualityEngine.check), because detecting
# a duplicate requires state (a memory of what's already been seen) that a
# single stateless rule function doesn't have access to.


# Rules run in this order; the engine stops at the first failure so each
# record gets exactly one reason.
COMPLETENESS_RULES = [
    rule_invoice_no_required,
    rule_unit_price_required,
    rule_invoice_date_required,
]

VALIDITY_RULES = [
    rule_quantity_sign_matches_cancellation,
    rule_unit_price_non_negative,
    rule_invoice_date_not_future,
]
