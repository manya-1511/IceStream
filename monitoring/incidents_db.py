"""
Database access for the `incidents` table (database/incidents_schema.sql).

Reuses the same engine/connection pattern as streaming/db.py — no new
connection machinery, just more queries against the same database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine


def create_incident(
    engine: Engine,
    incident_type: str,
    severity: str,
    error_rate: Optional[float],
    description: str,
    window_started_at: Optional[datetime] = None,
    window_ended_at: Optional[datetime] = None,
    records_in_window: Optional[int] = None,
    invalid_in_window: Optional[int] = None,
) -> int:
    """Inserts a new incident with status ACTIVE and returns its incident_id."""
    query = text(
        """
        INSERT INTO incidents
            (type, severity, error_rate, description, status,
             window_started_at, window_ended_at, records_in_window, invalid_in_window)
        VALUES
            (:type, :severity, :error_rate, :description, 'ACTIVE',
             :window_started_at, :window_ended_at, :records_in_window, :invalid_in_window)
        RETURNING incident_id
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            query,
            {
                "type": incident_type,
                "severity": severity,
                "error_rate": error_rate,
                "description": description,
                "window_started_at": window_started_at,
                "window_ended_at": window_ended_at,
                "records_in_window": records_in_window,
                "invalid_in_window": invalid_in_window,
            },
        )
        return result.scalar_one()


def update_incident_status(
    engine: Engine, incident_id: int, status: str, resolved: bool = False
) -> None:
    """
    Moves an incident to a new status. When status='RESOLVED', also stamps
    resolved_at with the current time.
    """
    if resolved:
        query = text(
            "UPDATE incidents SET status = :status, resolved_at = NOW() "
            "WHERE incident_id = :incident_id"
        )
    else:
        query = text("UPDATE incidents SET status = :status WHERE incident_id = :incident_id")

    with engine.begin() as conn:
        conn.execute(query, {"status": status, "incident_id": incident_id})


def get_incident(engine: Engine, incident_id: int):
    query = text("SELECT * FROM incidents WHERE incident_id = :incident_id")
    with engine.connect() as conn:
        return conn.execute(query, {"incident_id": incident_id}).mappings().first()


def get_active_incidents(engine: Engine):
    """Incidents that are ACTIVE or RECOVERING (i.e. not yet RESOLVED)."""
    query = text("SELECT * FROM incidents WHERE status != 'RESOLVED' ORDER BY started_at")
    with engine.connect() as conn:
        return conn.execute(query).mappings().all()
