"""
Database access for the streaming pipeline.

Reuses the same Settings/engine pattern already established in
backend/config.py and scripts/load_to_db.py — we don't reinvent connection
handling here, just point SQLAlchemy at the same database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from config import settings  # noqa: E402


def get_engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def preload_seen_keys(engine: Engine) -> Iterator[tuple]:
    """
    Yields the composite dedup key for every row already in valid_orders,
    so the QualityEngine's duplicate check survives restarts.
    """
    query = text(
        "SELECT invoice_no, stock_code, quantity, unit_price, invoice_date "
        "FROM valid_orders"
    )
    with engine.connect() as conn:
        for row in conn.execute(query):
            # unit_price comes back as Decimal; normalize to float so it
            # matches the in-memory keys built from CSV floats.
            yield (row.invoice_no, row.stock_code, row.quantity, float(row.unit_price), row.invoice_date)


def store_valid(engine: Engine, record: dict) -> None:
    query = text(
        """
        INSERT INTO valid_orders
            (invoice_no, stock_code, description, quantity, invoice_date,
             unit_price, customer_id, country, is_cancelled)
        VALUES
            (:invoice_no, :stock_code, :description, :quantity, :invoice_date,
             :unit_price, :customer_id, :country, :is_cancelled)
        """
    )
    with engine.begin() as conn:
        conn.execute(query, record)


def store_quarantine(
    engine: Engine, typed_record: dict, raw_record: dict, rule: str, reason: str
) -> None:
    """
    typed_record: the 9 order columns, coerced to correct types where
        possible. On a parse failure (validator couldn't trust the types at
        all), pass a dict of all-None values here — see run_stream.py.
    raw_record: the original row, preserved as JSON no matter what. This is
        what makes quarantine_orders forensically useful: even if every
        typed column above is NULL, you can still see exactly what arrived.
    """
    query = text(
        """
        INSERT INTO quarantine_orders
            (invoice_no, stock_code, description, quantity, invoice_date,
             unit_price, customer_id, country, is_cancelled,
             rule_triggered, reason, raw_record)
        VALUES
            (:invoice_no, :stock_code, :description, :quantity, :invoice_date,
             :unit_price, :customer_id, :country, :is_cancelled,
             :rule_triggered, :reason, :raw_record)
        """
    )
    params = dict(typed_record)
    params["rule_triggered"] = rule
    params["reason"] = reason
    params["raw_record"] = json.dumps(_json_safe(raw_record))
    with engine.begin() as conn:
        conn.execute(query, params)


def truncate_pipeline_tables(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE valid_orders RESTART IDENTITY"))
        conn.execute(text("TRUNCATE TABLE quarantine_orders RESTART IDENTITY"))


def _json_safe(record: dict) -> dict:
    """Make a record JSON-serializable (datetimes -> ISO strings)."""
    safe = {}
    for key, value in record.items():
        if hasattr(value, "isoformat"):
            safe[key] = value.isoformat()
        else:
            safe[key] = value
    return safe
