-- IceStream — Day 3 schema (additive; Day 1/2 schemas are untouched)
--
-- One incident row is created each time the circuit breaker
-- (monitoring/circuit_breaker.py) trips from HEALTHY/DEGRADED into
-- QUARANTINED because an anomaly was detected in a monitoring window
-- (monitoring/anomaly.py). The row is updated as recovery is attempted
-- (monitoring/recovery.py) and finally resolved.

CREATE TABLE IF NOT EXISTS incidents (
    incident_id     SERIAL PRIMARY KEY,

    started_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMP,                                  -- set when status becomes RESOLVED

    type            VARCHAR(20)     NOT NULL,                   -- 'ERROR_RATE' or 'VOLUME'
    severity        VARCHAR(10)     NOT NULL,                   -- 'LOW', 'MEDIUM', 'HIGH'
    error_rate      NUMERIC(5, 2),                               -- the window's error rate (%) that triggered this; NULL for a pure volume anomaly with no elevated error rate
    description     TEXT            NOT NULL,                   -- human-readable explanation, e.g. "error_rate 18.0% exceeded threshold 5.0%"
    status          VARCHAR(12)     NOT NULL DEFAULT 'ACTIVE',   -- ACTIVE, RECOVERING, RESOLVED

    -- Extra traceability fields (not required by the spec, but make the
    -- incident self-explanatory without cross-referencing logs)
    window_started_at   TIMESTAMP,
    window_ended_at      TIMESTAMP,
    records_in_window   INTEGER,
    invalid_in_window   INTEGER,

    CONSTRAINT chk_incidents_type   CHECK (type IN ('ERROR_RATE', 'VOLUME')),
    CONSTRAINT chk_incidents_status CHECK (status IN ('ACTIVE', 'RECOVERING', 'RESOLVED')),
    CONSTRAINT chk_incidents_severity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH'))
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
CREATE INDEX IF NOT EXISTS idx_incidents_started_at ON incidents (started_at);
