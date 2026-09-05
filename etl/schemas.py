"""
Canonical IceStream checkout-event schema.

This is the single, versioned event shape that every downstream component
(Kafka producer, Flink jobs, the data-quality engine, Iceberg tables) will
agree on. It is derived directly from the Olist Brazilian E-Commerce
dataset — see docs/data/dataset.md for the full source-field mapping.

Design rule (per Day 2 scope): every field is either
  (a) a real column from the Olist dataset,
  (b) a value directly derived from real Olist columns via documented,
      deterministic logic (e.g. transaction_id, subtotal, total_amount), or
  (c) a documented constant/None for a field the dataset does not provide
      (tax_amount, discount, device_type) — never a fabricated value.

No field in this file is populated with random or invented business data.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Real payment_type values observed in olist_order_payments_dataset.csv.
PaymentMethod = Literal["credit_card", "boleto", "voucher", "debit_card", "not_defined"]

CENT = Decimal("0.01")


def _round_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class CheckoutEvent(BaseModel):
    """One canonical checkout / order-line event.

    Granularity: one event = one distinct product within one order (Olist's
    order_items rows for the same (order_id, product_id) are aggregated
    into a single event with `quantity` = number of rows). This matches
    how a real checkout event stream is usually keyed — one line item per
    event — while staying faithful to what the dataset actually records.
    """

    model_config = ConfigDict(frozen=True)

    # --- Identity -----------------------------------------------------
    transaction_id: str = Field(
        ...,
        description=(
            "Deterministic UUID5 derived from (order_id, product_id). "
            "Not present in the source data — Olist has no single "
            "line-item transaction identifier, so one is derived "
            "reproducibly rather than invented per-run with random UUIDs."
        ),
    )
    order_id: str = Field(..., description="Real column: orders.order_id")
    customer_id: str = Field(
        ...,
        description=(
            "Real column: orders.customer_id. NOTE: in the real Olist "
            "dataset customer_id is order-scoped (a new id per order for "
            "the same physical person) — the dataset's customer_unique_id "
            "identifies the actual repeat customer. See docs/data/dataset.md."
        ),
    )

    # --- When / what ----------------------------------------------------
    timestamp: datetime = Field(..., description="Real column: orders.order_purchase_timestamp")
    product_id: str = Field(..., description="Real column: order_items.product_id")

    # --- Line-item economics --------------------------------------------
    quantity: int = Field(
        ...,
        ge=1,
        description="Derived: count of order_items rows sharing (order_id, product_id)",
    )
    unit_price: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Real column: order_items.price",
    )
    subtotal: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Derived: quantity * unit_price",
    )
    tax_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description=(
            "NOT AVAILABLE in the Olist dataset — Brazilian tax is embedded "
            "in price and never broken out. Always None; never fabricated."
        ),
    )
    discount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description=(
            "NOT AVAILABLE in the Olist dataset — there is no discount "
            "column. Always None; never fabricated."
        ),
    )
    shipping_amount: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description=(
            "Real column (summed across grouped rows): order_items.freight_value. "
            "Extra field beyond the base spec, included because it is real "
            "data already allocated per line item by Olist and materially "
            "affects total_amount."
        ),
    )
    total_amount: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Derived: subtotal + shipping_amount (tax_amount/discount excluded — unavailable)",
    )
    currency: Literal["BRL"] = Field(
        default="BRL",
        description="Constant: Olist is a Brazil-only marketplace; every transaction is in BRL.",
    )

    # --- Payment / geography / device -----------------------------------
    payment_method: PaymentMethod | None = Field(
        default=None,
        description=(
            "Derived: order_payments.payment_type for the order's highest-value "
            "payment row (an order can have multiple rows — e.g. a voucher plus "
            "a card charge — see docs/data/dataset.md for the selection rule). "
            "None if the order has no payment rows."
        ),
    )
    country: Literal["BR"] = Field(
        default="BR",
        description="Constant: Olist operates only in Brazil; not a per-record source column.",
    )
    device_type: Literal["web", "mobile", "app"] | None = Field(
        default=None,
        description=(
            "NOT AVAILABLE in the Olist dataset — no session/device tracking "
            "exists in this data. Always None for Day 2; reserved for a future "
            "day if a clearly-labeled synthetic augmentation is ever added."
        ),
    )

    # --- Extra real fields (beyond the base spec, justified by the dataset) --
    order_status: str = Field(..., description="Real column: orders.order_status")
    customer_state: str | None = Field(default=None, description="Real column: customers.customer_state")
    customer_city: str | None = Field(default=None, description="Real column: customers.customer_city")
    product_category: str | None = Field(
        default=None,
        description=(
            "Real column: products.product_category_name, translated to English via "
            "product_category_name_translation.csv where available (else the original "
            "Portuguese name; else None if the product is missing from products.csv)."
        ),
    )
    seller_id: str | None = Field(default=None, description="Real column: order_items.seller_id")

    # --- Cross-field consistency checks ---------------------------------
    @model_validator(mode="after")
    def _check_derived_amounts(self) -> "CheckoutEvent":
        expected_subtotal = _round_cents(self.unit_price * self.quantity)
        if _round_cents(self.subtotal) != expected_subtotal:
            raise ValueError(
                f"subtotal {self.subtotal} does not match quantity*unit_price "
                f"({expected_subtotal}) for transaction_id={self.transaction_id}"
            )

        expected_total = _round_cents(
            self.subtotal
            + self.shipping_amount
            + (self.tax_amount or Decimal("0"))
            - (self.discount or Decimal("0"))
        )
        if _round_cents(self.total_amount) != expected_total:
            raise ValueError(
                f"total_amount {self.total_amount} does not match "
                f"subtotal+shipping (+tax-discount) ({expected_total}) "
                f"for transaction_id={self.transaction_id}"
            )
        return self
