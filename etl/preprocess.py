"""
etl/preprocess.py — clean and join the raw Olist tables into canonical
IceStream checkout events.

Usage:
    python -m etl.preprocess                          # uses the fixture sample
    python -m etl.preprocess --raw-dir data/raw/olist  # uses the real download
    python -m etl.preprocess --raw-dir data/raw/olist --out-dir data/processed

What this does (see docs/data/dataset.md for the full field mapping):
    1. Load orders, order_items, order_payments, customers, and (optionally)
       products + category translation.
    2. Clean: drop rows missing required keys, coerce types, drop
       non-positive prices.
    3. Aggregate order_items by (order_id, product_id) -> quantity,
       unit_price, shipping_amount.
    4. Join in customer location, order status/timestamp, primary payment
       method, and product category.
    5. Derive transaction_id, subtotal, total_amount, currency, country.
    6. Validate every row against etl.schemas.CheckoutEvent and drop (with
       a logged reason) any row that fails.
    7. Write data/processed/checkout_events.parquet and .csv.

This script performs real cleaning/joining logic — it does not fabricate
any business values. Rows that cannot be derived from real source data are
dropped and reported, not filled in with invented numbers.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

import pandas as pd

from etl.constants import (
    CATEGORY_TRANSLATION_FILE,
    CUSTOMERS_FILE,
    FIXTURE_RAW_DIR,
    ICESTREAM_NAMESPACE,
    ORDER_ITEMS_FILE,
    ORDER_PAYMENTS_FILE,
    ORDERS_FILE,
    PROCESSED_DIR,
    PRODUCTS_FILE,
    REQUIRED_RAW_FILES,
)
from etl.schemas import CheckoutEvent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("etl.preprocess")


def _require_files(raw_dir: Path) -> None:
    missing = [f for f in REQUIRED_RAW_FILES if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required raw file(s) in {raw_dir}: {missing}. "
            f"Run scripts/download_dataset.sh first, or point --raw-dir at "
            f"the fixture sample: {FIXTURE_RAW_DIR}"
        )


def load_raw_tables(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Load the raw CSVs. Products / category translation are optional —
    a missing products file just means product_category ends up None."""
    _require_files(raw_dir)

    orders = pd.read_csv(
        raw_dir / ORDERS_FILE,
        parse_dates=["order_purchase_timestamp"],
    )
    order_items = pd.read_csv(raw_dir / ORDER_ITEMS_FILE)
    order_payments = pd.read_csv(raw_dir / ORDER_PAYMENTS_FILE)
    customers = pd.read_csv(raw_dir / CUSTOMERS_FILE)

    products_path = raw_dir / PRODUCTS_FILE
    products = pd.read_csv(products_path) if products_path.exists() else None

    translation_path = raw_dir / CATEGORY_TRANSLATION_FILE
    translation = pd.read_csv(translation_path) if translation_path.exists() else None

    return {
        "orders": orders,
        "order_items": order_items,
        "order_payments": order_payments,
        "customers": customers,
        "products": products,
        "translation": translation,
    }


def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    before = len(orders)
    df = orders.dropna(subset=["order_id", "customer_id", "order_purchase_timestamp"]).copy()
    df = df.drop_duplicates(subset=["order_id"])
    dropped = before - len(df)
    if dropped:
        logger.info("clean_orders: dropped %d row(s) missing required fields/duplicates", dropped)
    return df


def clean_order_items(order_items: pd.DataFrame) -> pd.DataFrame:
    before = len(order_items)
    df = order_items.dropna(subset=["order_id", "product_id", "price"]).copy()
    df = df[df["price"] > 0]
    dropped = before - len(df)
    if dropped:
        logger.info("clean_order_items: dropped %d row(s) with missing/non-positive price", dropped)
    return df


def aggregate_line_items(order_items: pd.DataFrame) -> pd.DataFrame:
    """One row per (order_id, product_id): quantity = row count, unit_price
    = the price (asserted constant within the group — Olist charges the
    same price per unit of a product within one order), shipping_amount =
    sum of freight_value across the grouped rows."""
    grouped = order_items.groupby(["order_id", "product_id"], as_index=False).agg(
        quantity=("order_item_id", "count"),
        unit_price=("price", "mean"),
        price_std=("price", "std"),
        shipping_amount=("freight_value", "sum"),
        seller_id=("seller_id", "first"),
    )
    inconsistent = grouped[grouped["price_std"].fillna(0) > 0.001]
    if len(inconsistent):
        logger.warning(
            "aggregate_line_items: %d (order_id, product_id) group(s) had "
            "inconsistent unit price across rows; used the mean. Example: %s",
            len(inconsistent),
            inconsistent.iloc[0][["order_id", "product_id"]].to_dict(),
        )
    return grouped.drop(columns=["price_std"])


def resolve_primary_payment(order_payments: pd.DataFrame) -> pd.DataFrame:
    """An order can have multiple payment rows (e.g. a voucher plus a card
    charge). We pick the row with the largest payment_value as the
    order's "primary" payment method — the one that represents most of
    what the customer actually paid. Ties broken by payment_sequential."""
    df = order_payments.sort_values(
        ["order_id", "payment_value", "payment_sequential"],
        ascending=[True, False, True],
    )
    primary = df.drop_duplicates(subset=["order_id"], keep="first")
    return primary[["order_id", "payment_type"]].rename(columns={"payment_type": "payment_method"})


def resolve_product_category(
    products: pd.DataFrame | None, translation: pd.DataFrame | None
) -> pd.DataFrame:
    """Real category name, translated to English where a translation
    exists; falls back to the original Portuguese name; None if the
    product isn't in products.csv at all."""
    if products is None:
        return pd.DataFrame(columns=["product_id", "product_category"])

    df = products[["product_id", "product_category_name"]].copy()
    if translation is not None:
        df = df.merge(translation, on="product_category_name", how="left")
        df["product_category"] = df["product_category_name_english"].fillna(
            df["product_category_name"]
        )
    else:
        df["product_category"] = df["product_category_name"]
    return df[["product_id", "product_category"]]


def build_canonical_frame(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    orders = clean_orders(tables["orders"])
    order_items = clean_order_items(tables["order_items"])
    line_items = aggregate_line_items(order_items)
    payments = resolve_primary_payment(tables["order_payments"])
    categories = resolve_product_category(tables["products"], tables["translation"])

    df = line_items.merge(
        orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp"]],
        on="order_id",
        how="inner",  # an order-item without a matching order is not a valid event
    )
    df = df.merge(
        tables["customers"][["customer_id", "customer_city", "customer_state"]],
        on="customer_id",
        how="left",
    )
    df = df.merge(payments, on="order_id", how="left")
    df = df.merge(categories, on="product_id", how="left")

    df["unit_price"] = df["unit_price"].round(2)
    df["shipping_amount"] = df["shipping_amount"].round(2)
    df["subtotal"] = (df["quantity"] * df["unit_price"]).round(2)
    df["total_amount"] = (df["subtotal"] + df["shipping_amount"]).round(2)
    df["currency"] = "BRL"
    df["country"] = "BR"
    df["tax_amount"] = None
    df["discount"] = None
    df["device_type"] = None

    df["transaction_id"] = df.apply(
        lambda r: str(uuid.uuid5(ICESTREAM_NAMESPACE, f"{r['order_id']}:{r['product_id']}")),
        axis=1,
    )
    df = df.rename(columns={"order_purchase_timestamp": "timestamp"})

    ordered_columns = [
        "transaction_id",
        "order_id",
        "customer_id",
        "timestamp",
        "product_id",
        "quantity",
        "unit_price",
        "subtotal",
        "tax_amount",
        "discount",
        "shipping_amount",
        "total_amount",
        "currency",
        "payment_method",
        "country",
        "device_type",
        "order_status",
        "customer_state",
        "customer_city",
        "product_category",
        "seller_id",
    ]
    return df[ordered_columns].sort_values("timestamp").reset_index(drop=True)


def validate_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Validate every row against CheckoutEvent. Returns (valid_rows_df,
    list_of_error_dicts) — invalid rows are dropped from the parquet/csv
    output but reported, never silently discarded."""
    valid_records = []
    errors = []
    for row in df.to_dict(orient="records"):
        try:
            event = CheckoutEvent.model_validate(row)
            valid_records.append(event.model_dump())
        except Exception as exc:  # noqa: BLE001
            errors.append({"row": row, "error": str(exc)})
    valid_df = pd.DataFrame(valid_records)
    return valid_df, errors


def write_outputs(df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "checkout_events.parquet"
    csv_path = out_dir / "checkout_events.csv"
    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)
    logger.info("Wrote %d record(s) to %s and %s", len(df), parquet_path, csv_path)


def run(raw_dir: Path, out_dir: Path) -> pd.DataFrame:
    logger.info("Loading raw tables from %s", raw_dir)
    tables = load_raw_tables(raw_dir)

    logger.info("Building canonical frame")
    raw_frame = build_canonical_frame(tables)
    logger.info("Built %d candidate record(s) before schema validation", len(raw_frame))

    valid_df, errors = validate_frame(raw_frame)
    if errors:
        logger.warning("%d record(s) failed schema validation and were dropped:", len(errors))
        for e in errors[:10]:
            logger.warning("  order_id=%s product_id=%s: %s", e["row"].get("order_id"), e["row"].get("product_id"), e["error"])

    write_outputs(valid_df, out_dir)
    logger.info(
        "Preprocessing complete: %d valid / %d total candidate record(s)",
        len(valid_df),
        len(raw_frame),
    )
    return valid_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean and canonicalize raw Olist data.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=FIXTURE_RAW_DIR,
        help=f"Directory containing the raw Olist CSVs (default: fixture sample at {FIXTURE_RAW_DIR})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=PROCESSED_DIR,
        help=f"Output directory for processed files (default: {PROCESSED_DIR})",
    )
    args = parser.parse_args()

    try:
        run(args.raw_dir, args.out_dir)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
