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


# --- Day 3 additions: circuit-breaker-aware quarantine handling ---------
#
# When the circuit breaker (monitoring/circuit_breaker.py) is open, records
# that individually PASS the quality engine are still held in
# quarantine_orders, tagged with rule_triggered='CIRCUIT_OPEN' rather than
# a real rule name, so recovery (monitoring/recovery.py) knows exactly
# which rows to re-check and which are genuinely-failing (left alone).

CIRCUIT_OPEN_RULE = "CIRCUIT_OPEN"


def get_circuit_open_records(engine: Engine):
    """
    Rows currently held in quarantine ONLY because the circuit was open
    (not because they individually failed a quality rule). These are the
    "affected records" recovery re-checks.
    """
    query = text(
        "SELECT id, invoice_no, stock_code, invoice_date "
        "FROM quarantine_orders WHERE rule_triggered = :rule "
        "ORDER BY id"
    )
    with engine.connect() as conn:
        return conn.execute(query, {"rule": CIRCUIT_OPEN_RULE}).mappings().all()


def delete_quarantine_row(engine: Engine, row_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM quarantine_orders WHERE id = :id"), {"id": row_id})


def update_quarantine_reason(engine: Engine, row_id: int, rule: str, reason: str) -> None:
    """Used when a re-checked CIRCUIT_OPEN row turns out to genuinely fail on retry."""
    query = text(
        "UPDATE quarantine_orders SET rule_triggered = :rule, reason = :reason "
        "WHERE id = :id"
    )
    with engine.begin() as conn:
        conn.execute(query, {"rule": rule, "reason": reason, "id": row_id})


def _json_safe(record: dict) -> dict:
    """Make a record JSON-serializable (datetimes -> ISO strings)."""
    safe = {}
    for key, value in record.items():
        if hasattr(value, "isoformat"):
            safe[key] = value.isoformat()
        else:
            safe[key] = value
    return safe
