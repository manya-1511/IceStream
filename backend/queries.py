"""
Queries backing the Day 4 dashboard API.

Every number here is computed directly from the same tables the streaming
engine (streaming/, monitoring/) writes to — valid_orders, quarantine_orders,
incidents. There is no separate "metrics store": the API is a read-only,
on-demand view over the pipeline's actual state. Nothing here is
hardcoded or simulated.

The API process and the streaming engine are separate processes that only
share the database — this file's job is turning raw rows into the shapes
the dashboard needs, the same way streaming/db.py and monitoring/incidents_db.py
already do for their own callers.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Window used for "live" activity numbers (events/sec, and the recent-window
# quality score/error rate). 30s is long enough to smooth over a single
# record's noise but short enough to feel real-time.
LIVE_WINDOW_SECONDS = 30

# Maps a rule function name (see quality/rules.py) or synthetic rule name
# (see streaming/db.py, monitoring/pipeline.py) to the real dataset field it
# concerns, for the incident panel's "Affected Field" line.
RULE_TO_FIELD = {
    "rule_invoice_no_required": "invoice_no",
    "rule_unit_price_required": "unit_price",
    "rule_invoice_date_required": "invoice_date",
    "rule_quantity_sign_matches_cancellation": "quantity",
    "rule_unit_price_non_negative": "unit_price",
    "rule_invoice_date_not_future": "invoice_date",
    "rule_duplicate_line_item": "invoice_no + stock_code",
    "PARSE_ERROR": "unparseable row",
}


def get_summary(engine: Engine) -> dict:
    with engine.connect() as conn:
        totals = conn.execute(
            text(
                "SELECT "
                "  (SELECT COUNT(*) FROM valid_orders) AS valid_total, "
                "  (SELECT COUNT(*) FROM quarantine_orders) AS quarantine_total, "
                "  (SELECT COUNT(*) FROM incidents WHERE status != 'RESOLVED') AS active_incidents"
            )
        ).mappings().one()

        recent = conn.execute(
            text(
                "SELECT "
                "  COUNT(*) FILTER (WHERE is_valid) AS valid_recent, "
                "  COUNT(*) AS total_recent "
                "FROM ( "
                "  SELECT TRUE AS is_valid FROM valid_orders WHERE checked_at >= NOW() - make_interval(secs => :window) "
                "  UNION ALL "
                "  SELECT FALSE AS is_valid FROM quarantine_orders WHERE checked_at >= NOW() - make_interval(secs => :window) "
                ") recent_events"
            ),
            {"window": LIVE_WINDOW_SECONDS},
        ).mappings().one()

        incident_state = conn.execute(
            text(
                "SELECT status FROM incidents WHERE status != 'RESOLVED' "
                "ORDER BY CASE status WHEN 'ACTIVE' THEN 0 WHEN 'RECOVERING' THEN 1 ELSE 2 END "
                "LIMIT 1"
            )
        ).scalar_one_or_none()

    valid_total = totals["valid_total"]
    quarantine_total = totals["quarantine_total"]
    total_processed = valid_total + quarantine_total

    total_recent = recent["total_recent"]
    valid_recent = recent["valid_recent"]

    events_per_sec = round(total_recent / LIVE_WINDOW_SECONDS, 2)

    # Prefer the recent window for quality score/error rate (it reflects
    # what's happening *now*); fall back to all-time totals when the stream
    # isn't currently active, so the dashboard doesn't show a misleading 0%.
    if total_recent > 0:
        quality_score = round((valid_recent / total_recent) * 100, 2)
    elif total_processed > 0:
        quality_score = round((valid_total / total_processed) * 100, 2)
    else:
        quality_score = 100.0
    error_rate = round(100 - quality_score, 2)

    if incident_state == "ACTIVE":
        status = "QUARANTINED"
    elif incident_state == "RECOVERING":
        status = "RECOVERING"
    elif total_recent > 0 and valid_recent < total_recent:
        status = "DEGRADED"
    else:
        status = "HEALTHY"

    return {
        "events_per_sec": events_per_sec,
        "total_processed": total_processed,
        "quality_score": quality_score,
        "error_rate": error_rate,
        "quarantined_count": quarantine_total,
        "active_incidents": totals["active_incidents"],
        "status": status,
    }


def get_timeseries(engine: Engine, window_minutes: int, bucket_seconds: int) -> list[dict]:
    """
    Buckets valid_orders/quarantine_orders into `bucket_seconds`-wide
    windows over the last `window_minutes`, and returns events/sec +
    quality score per bucket. Empty buckets get quality_score=None (not a
    fabricated 100%) so the frontend can render a gap instead of a lie.
    """
    query = text(
        """
        WITH buckets AS (
            SELECT generate_series(
                date_trunc('second', NOW()) - make_interval(mins => :window_minutes),
                date_trunc('second', NOW()),
                make_interval(secs => :bucket_seconds)
            ) AS bucket_start
        ),
        events AS (
            SELECT checked_at, TRUE AS is_valid FROM valid_orders
            WHERE checked_at >= NOW() - make_interval(mins => :window_minutes)
            UNION ALL
            SELECT checked_at, FALSE AS is_valid FROM quarantine_orders
            WHERE checked_at >= NOW() - make_interval(mins => :window_minutes)
        )
        SELECT
            buckets.bucket_start,
            COUNT(events.checked_at) AS total,
            COUNT(events.checked_at) FILTER (WHERE events.is_valid) AS valid_count
        FROM buckets
        LEFT JOIN events
            ON events.checked_at >= buckets.bucket_start
           AND events.checked_at <  buckets.bucket_start + make_interval(secs => :bucket_seconds)
        GROUP BY buckets.bucket_start
        ORDER BY buckets.bucket_start
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            query, {"window_minutes": window_minutes, "bucket_seconds": bucket_seconds}
        ).mappings().all()

    points = []
    for row in rows:
        total = row["total"]
        valid = row["valid_count"]
        points.append(
            {
                "timestamp": row["bucket_start"].isoformat(),
                "events_per_sec": round(total / bucket_seconds, 2),
                "quality_score": round((valid / total) * 100, 2) if total else None,
            }
        )
    return points


def get_latest_point(engine: Engine, bucket_seconds: int) -> dict:
    """The single most recent bucket — used by the WebSocket tick to append one live point."""
    points = get_timeseries(engine, window_minutes=max(1, bucket_seconds // 60 + 1), bucket_seconds=bucket_seconds)
    return points[-1] if points else {"timestamp": None, "events_per_sec": 0.0, "quality_score": None}


def get_incidents(engine: Engine, limit: int = 20) -> list[dict]:
    query = text(
        """
        SELECT incident_id, started_at, resolved_at, type, severity,
               error_rate, description, status,
               window_started_at, window_ended_at
        FROM incidents
        ORDER BY started_at DESC
        LIMIT :limit
        """
    )
    field_query = text(
        """
        SELECT rule_triggered, COUNT(*) AS n
        FROM quarantine_orders
        WHERE checked_at >= :window_started AND checked_at <= :window_ended
          AND rule_triggered != 'CIRCUIT_OPEN'
        GROUP BY rule_triggered
        ORDER BY n DESC
        LIMIT 1
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()

        incidents = []
        for row in rows:
            affected_field = None
            if row["window_started_at"] and row["window_ended_at"]:
                top_rule = conn.execute(
                    field_query,
                    {
                        "window_started": row["window_started_at"],
                        "window_ended": row["window_ended_at"],
                    },
                ).mappings().first()
                if top_rule:
                    affected_field = RULE_TO_FIELD.get(top_rule["rule_triggered"], top_rule["rule_triggered"])

            incidents.append(
                {
                    "incident_id": row["incident_id"],
                    "started_at": row["started_at"].isoformat(),
                    "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
                    "type": row["type"],
                    "severity": row["severity"],
                    "error_rate": float(row["error_rate"]) if row["error_rate"] is not None else None,
                    "description": row["description"],
                    "status": row["status"],
                    "affected_field": affected_field,
                }
            )
    return incidents
