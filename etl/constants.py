"""Shared constants and paths for the etl/ pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path

# Repo-relative paths. All etl scripts accept a --raw-dir / --out-dir
# override, but default to these so `python -m etl.preprocess` just works.
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "olist"
FIXTURE_RAW_DIR = REPO_ROOT / "data" / "samples" / "olist_raw_fixture"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
EVENTS_DIR = PROCESSED_DIR / "events"
SAMPLES_DIR = REPO_ROOT / "data" / "samples"

# Deterministic namespace for deriving transaction_id via UUID5. Fixed so
# the same (order_id, product_id) always produces the same transaction_id
# across repeated runs — important for future idempotent Kafka replay.
ICESTREAM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "icestream.dev")

# Real Olist source file names (must match the Kaggle download exactly).
ORDERS_FILE = "olist_orders_dataset.csv"
ORDER_ITEMS_FILE = "olist_order_items_dataset.csv"
ORDER_PAYMENTS_FILE = "olist_order_payments_dataset.csv"
CUSTOMERS_FILE = "olist_customers_dataset.csv"
PRODUCTS_FILE = "olist_products_dataset.csv"
CATEGORY_TRANSLATION_FILE = "product_category_name_translation.csv"

REQUIRED_RAW_FILES = [
    ORDERS_FILE,
    ORDER_ITEMS_FILE,
    ORDER_PAYMENTS_FILE,
    CUSTOMERS_FILE,
]
OPTIONAL_RAW_FILES = [PRODUCTS_FILE, CATEGORY_TRANSLATION_FILE]
