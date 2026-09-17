"""
Load data/processed/orders_clean.csv into the PostgreSQL `orders` table.

Run scripts/download_dataset.py and scripts/preprocess_data.py first.
Requires the `orders` table to already exist (see database/schema.sql,
applied automatically by docker-compose on first startup).

Usage:
    python scripts/load_to_db.py
    python scripts/load_to_db.py --truncate   # wipe the table first
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# Reuse the same settings the backend uses, so the DB URL is defined once.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from config import settings  # noqa: E402

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
BATCH_SIZE = 5000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--truncate", action="store_true", help="Delete existing rows before loading."
    )
    args = parser.parse_args()

    clean_path = PROCESSED_DIR / "orders_clean.csv"
    if not clean_path.exists():
        print(
            f"ERROR: {clean_path} not found. Run scripts/preprocess_data.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Reading {clean_path}...")
    df = pd.read_csv(clean_path, parse_dates=["invoice_date"])
    print(f"Loaded {len(df):,} rows from CSV.")

    engine = create_engine(settings.database_url)

    if args.truncate:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE orders RESTART IDENTITY"))
        print("Truncated existing orders table.")

    print(f"Inserting into PostgreSQL in batches of {BATCH_SIZE}...")
    df.to_sql(
        "orders",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=BATCH_SIZE,
    )

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar_one()

    print(f"Done. orders table now has {count:,} rows.")


if __name__ == "__main__":
    main()
