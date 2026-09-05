"""Unit tests for etl.schemas.CheckoutEvent — the canonical event shape."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from etl.schemas import CheckoutEvent

VALID_BASE: dict = {
    "transaction_id": "11111111-1111-5111-8111-111111111111",
    "order_id": "ord_0001",
    "customer_id": "cust_0001",
    "timestamp": "2017-01-05T10:15:23",
    "product_id": "prod_0001",
    "quantity": 2,
    "unit_price": "89.90",
    "subtotal": "179.80",
    "shipping_amount": "30.20",
    "total_amount": "210.00",
    "currency": "BRL",
    "payment_method": "credit_card",
    "country": "BR",
    "order_status": "delivered",
}


def test_valid_event_round_trips():
    event = CheckoutEvent.model_validate(VALID_BASE)
    assert event.transaction_id == VALID_BASE["transaction_id"]
    assert event.quantity == 2
    assert event.unit_price == Decimal("89.90")
    assert event.currency == "BRL"
    assert event.country == "BR"
    # Fields unavailable in the source dataset must default to None, never
    # be silently fabricated.
    assert event.tax_amount is None
    assert event.discount is None
    assert event.device_type is None


def test_missing_required_field_rejected():
    bad = {k: v for k, v in VALID_BASE.items() if k != "order_id"}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_non_positive_unit_price_rejected():
    bad = {**VALID_BASE, "unit_price": "0.00"}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_zero_quantity_rejected():
    bad = {**VALID_BASE, "quantity": 0}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_subtotal_mismatch_rejected():
    bad = {**VALID_BASE, "subtotal": "999.99"}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_total_amount_mismatch_rejected():
    bad = {**VALID_BASE, "total_amount": "1.00"}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_invalid_currency_rejected():
    bad = {**VALID_BASE, "currency": "USD"}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_invalid_country_rejected():
    bad = {**VALID_BASE, "country": "US"}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_invalid_payment_method_rejected():
    bad = {**VALID_BASE, "payment_method": "crypto"}
    with pytest.raises(ValidationError):
        CheckoutEvent.model_validate(bad)


def test_payment_method_none_is_allowed():
    ok = {**VALID_BASE, "payment_method": None}
    event = CheckoutEvent.model_validate(ok)
    assert event.payment_method is None


def test_total_amount_accounts_for_tax_and_discount_when_present():
    ok = {
        **VALID_BASE,
        "tax_amount": "5.00",
        "discount": "2.00",
        "total_amount": "213.00",  # 179.80 + 30.20 + 5.00 - 2.00
    }
    event = CheckoutEvent.model_validate(ok)
    assert event.total_amount == Decimal("213.00")


def test_model_is_frozen():
    event = CheckoutEvent.model_validate(VALID_BASE)
    with pytest.raises(ValidationError):
        event.quantity = 5  # type: ignore[misc]
