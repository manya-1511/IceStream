"""
Reads data/processed/orders_clean.csv — the REAL dataset produced by
scripts/preprocess_data.py — and yields rows one at a time, ordered by
invoice_date, so the stream replays history in the order it actually
happened.

This module never generates or invents records. It only reads what's
already on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

DEFAULT_SOURCE = Path(__file__).resolve().parent.parent / "data" / "processed" / "orders_clean.csv"


def read_orders(source: Path = DEFAULT_SOURCE, limit: Optional[int] = None) -> Iterator[dict]:
    """
    Yields one dict per row from the real processed dataset, sorted by
    invoice_date ascending. Each dict has the same fields as orders_clean.csv:
    invoice_no, stock_code, description, quantity, invoice_date, unit_price,
    customer_id, country, is_cancelled.

    `limit`, if given, stops after that many rows — useful for quick manual
    tests instead of replaying all ~540k+ rows.
    """
    if not source.exists():
        raise FileNotFoundError(
            f"{source} not found. Run scripts/download_dataset.py and "
            "scripts/preprocess_data.py first."
        )

    # invoice_no and stock_code are identifiers, not numbers — but pandas
    # will silently infer int64 for them whenever a file/slice happens to
    # contain no letters (most invoice numbers are numeric; only
    # cancellations start with 'C'). Forcing str here keeps their type
    # consistent with the VARCHAR columns in Postgres, which matters for
    # the duplicate-detection key in quality/engine.py.
    df = pd.read_csv(
        source,
        parse_dates=["invoice_date"],
        dtype={"invoice_no": str, "stock_code": str},
    )
    df = df.sort_values("invoice_date", kind="stable").reset_index(drop=True)

    if limit is not None:
        df = df.head(limit)

    for _, row in df.iterrows():
        yield row.to_dict()
