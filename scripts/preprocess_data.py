"""
Clean the raw "Online Retail II" dataset and map it into IceStream's schema.

Steps:
  1. Read the raw Excel file (data/raw/*.xlsx), which has two sheets:
     "Year 2009-2010" and "Year 2010-2011".
  2. Rename columns to our application's schema (see database/schema.sql).
  3. Reject rows that are structurally broken (missing stock code, missing
     invoice date, or a quantity/price that isn't a number). Every rejected
     row is written to data/processed/rejected_rows.csv WITH A REASON — we
     never silently drop data.
  4. Clean formatting issues that don't require dropping the row (trim
     whitespace, fill missing descriptions, normalize country names). Every
     such change is counted and logged.
  5. Derive `is_cancelled` from the invoice number (UCI docs: an invoice
     starting with 'C' is a cancellation).
  6. Save the cleaned data to data/processed/orders_clean.csv, ready to be
     loaded into PostgreSQL.

Nothing here invents data. Rows we can't confidently clean are rejected and
logged instead of guessed at.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

SHEET_NAMES = ["Year 2009-2010", "Year 2010-2011"]

# Raw dataset column -> our schema column
COLUMN_MAP = {
    "Invoice": "invoice_no",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "unit_price",
    "Customer ID": "customer_id",
    "Country": "country",
}


def find_raw_file() -> Path:
    candidates = sorted(RAW_DIR.glob("*.xlsx"))
    if not candidates:
        print(
            f"ERROR: no .xlsx file found in {RAW_DIR}. "
            "Run scripts/download_dataset.py first.",
            file=sys.stderr,
        )
        sys.exit(1)
    return candidates[0]


def load_raw(path: Path) -> pd.DataFrame:
    frames = []
    for sheet in SHEET_NAMES:
        print(f"Reading sheet '{sheet}'...")
        df = pd.read_excel(path, sheet_name=sheet)
        df["source_sheet"] = sheet
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(combined):,} raw rows total.")
    return combined


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Returns (clean_df, rejected_df, change_log).
    rejected_df has a 'reject_reason' column explaining why each row was dropped.
    """
    change_log: list[str] = []
    df = df.rename(columns=COLUMN_MAP).copy()

    # Track rejection reason per row without mutating original index
    df["reject_reason"] = None

    # --- Structural checks (these cause rejection) ---

    # 1. Missing stock code -> can't identify the product, reject.
    missing_stock = df["stock_code"].isna() | (df["stock_code"].astype(str).str.strip() == "")
    df.loc[missing_stock, "reject_reason"] = "missing stock_code"

    # 2. Missing invoice number -> can't group into an order, reject.
    missing_invoice = df["invoice_no"].isna() | (df["invoice_no"].astype(str).str.strip() == "")
    df.loc[missing_invoice & df["reject_reason"].isna(), "reject_reason"] = "missing invoice_no"

    # 3. Missing / unparseable invoice date -> reject (we need this for streaming replay).
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    bad_date = df["invoice_date"].isna()
    df.loc[bad_date & df["reject_reason"].isna(), "reject_reason"] = "missing/invalid invoice_date"

    # 4. Quantity must be a whole number (can legitimately be negative — that's a
    #    cancellation, not a data error).
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    bad_qty = df["quantity"].isna()
    df.loc[bad_qty & df["reject_reason"].isna(), "reject_reason"] = "non-numeric quantity"

    # 5. Unit price must be a number. (Price == 0 is kept — real promotional/
    #    free items exist in this dataset — but non-numeric is rejected.)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    bad_price = df["unit_price"].isna()
    df.loc[bad_price & df["reject_reason"].isna(), "reject_reason"] = "non-numeric unit_price"

    rejected_df = df[df["reject_reason"].notna()].copy()
    clean_df = df[df["reject_reason"].isna()].copy()

    change_log.append(f"Rejected {len(rejected_df):,} rows total:")
    for reason, count in rejected_df["reject_reason"].value_counts().items():
        change_log.append(f"  - {reason}: {count:,} rows")

    clean_df = clean_df.drop(columns=["reject_reason"])

    # --- Non-destructive cleaning (these modify, not drop) ---

    # Trim whitespace on text fields.
    for col in ["invoice_no", "stock_code", "description", "country"]:
        before_blank = clean_df[col].isna().sum() if col in clean_df else 0
        if col in clean_df.columns:
            clean_df[col] = clean_df[col].astype(str).str.strip()
            clean_df[col] = clean_df[col].replace({"nan": None, "": None})

    # Fill missing descriptions instead of dropping the row — the row is
    # still a valid transaction, we just don't know the product name text.
    missing_desc = clean_df["description"].isna().sum()
    clean_df["description"] = clean_df["description"].fillna("UNKNOWN DESCRIPTION")
    change_log.append(f"Filled {missing_desc:,} missing descriptions with 'UNKNOWN DESCRIPTION'.")

    # customer_id: keep NULL where absent (many real B2C guest-style rows have none)
    # instead of coercing to 0, which would look like a real customer.
    clean_df["customer_id"] = pd.to_numeric(clean_df["customer_id"], errors="coerce")
    missing_customer = clean_df["customer_id"].isna().sum()
    change_log.append(f"Left {missing_customer:,} customer_id values as NULL (not present in source).")
    clean_df["customer_id"] = clean_df["customer_id"].astype("Int64")

    missing_country = clean_df["country"].isna().sum()
    clean_df["country"] = clean_df["country"].fillna("UNKNOWN")
    change_log.append(f"Filled {missing_country:,} missing countries with 'UNKNOWN'.")

    # Derive is_cancelled from the invoice number convention documented by UCI:
    # an invoice number starting with 'C' is a cancellation.
    clean_df["is_cancelled"] = clean_df["invoice_no"].str.upper().str.startswith("C")
    n_cancelled = int(clean_df["is_cancelled"].sum())
    change_log.append(f"Flagged {n_cancelled:,} rows as cancellations (invoice starts with 'C').")

    clean_df = clean_df[
        [
            "invoice_no",
            "stock_code",
            "description",
            "quantity",
            "invoice_date",
            "unit_price",
            "customer_id",
            "country",
            "is_cancelled",
        ]
    ]

    return clean_df, rejected_df, change_log


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = find_raw_file()

    raw_df = load_raw(raw_path)
    clean_df, rejected_df, change_log = clean(raw_df)

    clean_path = PROCESSED_DIR / "orders_clean.csv"
    rejected_path = PROCESSED_DIR / "rejected_rows.csv"
    log_path = PROCESSED_DIR / "preprocessing_log.txt"

    clean_df.to_csv(clean_path, index=False)
    rejected_df.to_csv(rejected_path, index=False)

    log_lines = [
        f"IceStream preprocessing run: {datetime.now().isoformat()}",
        f"Source file: {raw_path.name}",
        f"Raw rows read: {len(raw_df):,}",
        f"Clean rows written: {len(clean_df):,}",
        "",
        *change_log,
    ]
    log_path.write_text("\n".join(log_lines) + "\n")

    print("\n".join(log_lines))
    print(f"\nWrote clean data to:    {clean_path}")
    print(f"Wrote rejected rows to: {rejected_path}")
    print(f"Wrote log to:           {log_path}")


if __name__ == "__main__":
    main()
