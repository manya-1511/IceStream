"""Tests for etl.preprocess — run against the small committed fixture
dataset (data/samples/olist_raw_fixture/), never against the real
100k-order Kaggle download."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl.preprocess import load_raw_tables, run
from etl.schemas import CheckoutEvent


def test_load_raw_tables_reads_all_fixture_files(fixture_raw_dir: Path):
    tables = load_raw_tables(fixture_raw_dir)
    assert len(tables["orders"]) == 15
    assert len(tables["order_items"]) == 21
    assert len(tables["order_payments"]) == 16
    assert len(tables["customers"]) == 15
    assert tables["products"] is not None and len(tables["products"]) == 10


def test_run_produces_expected_record_count(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = run(fixture_raw_dir, tmp_out_dir)
    # 21 raw order_item rows; three orders each collapse a 2-3 row same-
    # product group into 1 event -> 21 - 1 - 2 - 1 = 17 canonical events.
    assert len(df) == 17
    assert (tmp_out_dir / "checkout_events.parquet").exists()
    assert (tmp_out_dir / "checkout_events.csv").exists()


def test_every_output_row_is_schema_valid(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = run(fixture_raw_dir, tmp_out_dir)
    for row in df.to_dict(orient="records"):
        CheckoutEvent.model_validate(row)  # raises if invalid


def test_quantity_aggregation_for_repeated_product(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = run(fixture_raw_dir, tmp_out_dir)
    row = df[(df["order_id"] == "ord_0001") & (df["product_id"] == "prod_0001")].iloc[0]
    assert row["quantity"] == 2
    assert float(row["subtotal"]) == 179.80


def test_primary_payment_picks_highest_value(fixture_raw_dir: Path, tmp_out_dir: Path):
    """ord_0007 has a voucher (12.20) and a credit_card (400.00) payment row
    — the credit_card row should win as the primary payment_method."""
    df = run(fixture_raw_dir, tmp_out_dir)
    rows = df[df["order_id"] == "ord_0007"]
    assert (rows["payment_method"] == "credit_card").all()


def test_canceled_order_still_produces_an_event(fixture_raw_dir: Path, tmp_out_dir: Path):
    """A checkout event happens at purchase time — order_status is
    informational, not a filter."""
    df = run(fixture_raw_dir, tmp_out_dir)
    canceled = df[df["order_id"] == "ord_0006"]
    assert len(canceled) == 1
    assert canceled.iloc[0]["order_status"] == "canceled"


def test_output_sorted_by_timestamp(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = run(fixture_raw_dir, tmp_out_dir)
    timestamps = pd.to_datetime(df["timestamp"])
    assert list(timestamps) == sorted(timestamps)


def test_currency_and_country_are_constant(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = run(fixture_raw_dir, tmp_out_dir)
    assert (df["currency"] == "BRL").all()
    assert (df["country"] == "BR").all()


def test_tax_discount_device_type_are_always_null(fixture_raw_dir: Path, tmp_out_dir: Path):
    """These fields have no source in the Olist dataset — they must never
    be silently populated with fabricated values."""
    df = run(fixture_raw_dir, tmp_out_dir)
    assert df["tax_amount"].isna().all()
    assert df["discount"].isna().all()
    assert df["device_type"].isna().all()


def test_product_category_translated_to_english(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = run(fixture_raw_dir, tmp_out_dir)
    row = df[df["product_id"] == "prod_0001"].iloc[0]
    assert row["product_category"] == "health_beauty"


def test_missing_translation_falls_back_to_portuguese_name(fixture_raw_dir: Path, tmp_out_dir: Path):
    """product_category_name_translation.csv fixture intentionally omits
    relogios_presentes to exercise the fallback to the original name."""
    df = run(fixture_raw_dir, tmp_out_dir)
    row = df[df["product_id"] == "prod_0006"].iloc[0]  # relogios_presentes — not in translation fixture
    assert row["product_category"] == "relogios_presentes"
