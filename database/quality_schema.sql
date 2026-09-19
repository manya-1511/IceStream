-- IceStream — Day 2 schema (additive; Day 1's schema.sql / orders table is untouched)
--
-- The streaming engine (streaming/run_stream.py) replays real orders one at
-- a time through the data quality engine (quality/engine.py). Each record
-- lands in exactly one of these two tables:
--
--   valid_orders       — passed every quality rule
--   quarantine_orders  — failed at least one rule, with the reason kept
--
-- `orders` (Day 1) stays as the full bulk-loaded reference copy of the
-- dataset; these two tables are the *output* of the real-time pipeline.

CREATE TABLE IF NOT EXISTS valid_orders (
    id              SERIAL PRIMARY KEY,

    invoice_no      VARCHAR(20)     NOT NULL,
    stock_code      VARCHAR(20)     NOT NULL,
    description     TEXT,
    quantity        INTEGER         NOT NULL,
    invoice_date    TIMESTAMP       NOT NULL,
    unit_price      NUMERIC(10, 2)  NOT NULL,
    customer_id     INTEGER,
    country         VARCHAR(100),
    is_cancelled    BOOLEAN         NOT NULL DEFAULT FALSE,

    checked_at      TIMESTAMP       NOT NULL DEFAULT NOW()  -- when the quality engine processed it
);

CREATE INDEX IF NOT EXISTS idx_valid_orders_invoice_date ON valid_orders (invoice_date);
CREATE INDEX IF NOT EXISTS idx_valid_orders_stock_code    ON valid_orders (stock_code);
CREATE INDEX IF NOT EXISTS idx_valid_orders_invoice_no    ON valid_orders (invoice_no);

-- Quarantine holds records that failed a quality rule. Columns mirror
-- valid_orders but are ALL nullable — the whole point of quarantine is that
-- one of these fields might be exactly what's missing or malformed, and we
-- must still be able to store the record instead of losing it.
CREATE TABLE IF NOT EXISTS quarantine_orders (
    id              SERIAL PRIMARY KEY,

    invoice_no      VARCHAR(20),
    stock_code      VARCHAR(20),
    description     TEXT,
    quantity        INTEGER,
    invoice_date    TIMESTAMP,
    unit_price      NUMERIC(10, 2),
    customer_id     INTEGER,
    country         VARCHAR(100),
    is_cancelled    BOOLEAN,

    rule_triggered  VARCHAR(50)     NOT NULL,   -- e.g. 'unit_price_non_negative'
    reason          TEXT            NOT NULL,   -- human-readable explanation
    raw_record      JSONB           NOT NULL,   -- full original row, nothing lost even if typed columns above are NULL

    checked_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quarantine_orders_invoice_date   ON quarantine_orders (invoice_date);
CREATE INDEX IF NOT EXISTS idx_quarantine_orders_rule_triggered ON quarantine_orders (rule_triggered);
