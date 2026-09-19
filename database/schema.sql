-- IceStream  
--
-- Only one table for now: orders. It mirrors the real "Online Retail II"
-- dataset (see docs/DATASET.md) so the preprocessing script can load
-- cleaned rows directly into it. More tables (data quality events, alerts,
-- customers, products...) will be added in later days as they're needed.

CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,

    -- Original dataset fields
    invoice_no      VARCHAR(20)     NOT NULL,
    stock_code      VARCHAR(20)     NOT NULL,
    description     TEXT,
    quantity        INTEGER         NOT NULL,
    invoice_date    TIMESTAMP       NOT NULL,
    unit_price      NUMERIC(10, 2)  NOT NULL,
    customer_id     INTEGER,                    -- nullable: many real rows have no customer id
    country         VARCHAR(100),

    -- Derived by our pipeline
    is_cancelled    BOOLEAN         NOT NULL DEFAULT FALSE,  -- InvoiceNo starting with 'C'
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- Indexes for the queries we already know we'll need:
-- time-ordered streaming replay, and per-product / per-customer lookups.
CREATE INDEX IF NOT EXISTS idx_orders_invoice_date ON orders (invoice_date);
CREATE INDEX IF NOT EXISTS idx_orders_stock_code    ON orders (stock_code);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id   ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_invoice_no    ON orders (invoice_no);
