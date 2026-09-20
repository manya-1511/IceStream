# Database Schema

Only one table exists so far: `orders`. Its full definition lives in
[`database/schema.sql`](../database/schema.sql) — this doc explains the
*reasoning* behind it.

## `orders`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | no | Internal surrogate key. |
| `invoice_no` | `VARCHAR(20)` | no | Maps from `Invoice`. Not unique per row — one invoice has multiple line items. |
| `stock_code` | `VARCHAR(20)` | no | Maps from `StockCode`. |
| `description` | `TEXT` | yes | Maps from `Description`. Missing values filled with `'UNKNOWN DESCRIPTION'` during preprocessing. |
| `quantity` | `INTEGER` | no | Maps from `Quantity`. Can be negative (cancellations). |
| `invoice_date` | `TIMESTAMP` | no | Maps from `InvoiceDate`. Indexed — this is what the streaming engine will replay in order. |
| `unit_price` | `NUMERIC(10,2)` | no | Maps from `Price`. |
| `customer_id` | `INTEGER` | yes | Maps from `Customer ID`. Legitimately `NULL` for guest-style rows — never defaulted to `0`. |
| `country` | `VARCHAR(100)` | yes | Maps from `Country`. Missing filled with `'UNKNOWN'`. |
| `is_cancelled` | `BOOLEAN` | no | Derived: `TRUE` if `invoice_no` starts with `'C'` (UCI's documented cancellation convention). |
| `created_at` | `TIMESTAMP` | no | When the row was inserted into *our* database (default `NOW()`), not part of the source data. |

### Indexes

- `idx_orders_invoice_date` — the streaming engine replays rows ordered by
  this column.
- `idx_orders_stock_code`, `idx_orders_customer_id`, `idx_orders_invoice_no`
  — for the per-product/per-customer/per-invoice lookups the quality engine
  and dashboard will need starting Day 2–3.

### Deliberately not built yet

- No `customers` or `products` tables — we don't need normalized lookups
  yet, and adding them before they're needed would just be extra schema to
  maintain. They're an obvious future refactor once the streaming/quality
  engines are running.

## `valid_orders` and `quarantine_orders` (Day 2)

Full definition: [`database/quality_schema.sql`](../database/quality_schema.sql).
Design reasoning for the rules that populate these tables:
[`docs/QUALITY_RULES.md`](QUALITY_RULES.md).

These are the *output* of the streaming pipeline (`streaming/run_stream.py`):
every record read from `data/processed/orders_clean.csv` lands in exactly
one of the two, depending on whether it passed every data quality rule.
`orders` (Day 1) is untouched — it stays as the full bulk-loaded reference
copy of the dataset.

**`valid_orders`** — same shape as `orders`, plus `checked_at` (when the
quality engine processed it, as opposed to `orders.created_at`, which is
when Day 1's bulk loader ran).

**`quarantine_orders`** — same order columns, but every one of them is
**nullable**, because the whole point of quarantine is that one of those
fields might be exactly what's missing or malformed. Three extra columns
record *why* the record is here:

| Column | Notes |
|---|---|
| `rule_triggered` | The name of the rule function that failed, e.g. `rule_unit_price_non_negative`. |
| `reason` | Human-readable explanation, e.g. `unit_price is negative (-11062.06)`. |
| `raw_record` | `JSONB` snapshot of the original row, preserved no matter what — even if every typed column above is `NULL` because the row couldn't be parsed at all. |

## `incidents` (Day 3)

Full definition: [`database/incidents_schema.sql`](../database/incidents_schema.sql).
Design reasoning: [`docs/ANOMALY_DETECTION.md`](ANOMALY_DETECTION.md).

One row per detected anomaly (error-rate or volume), created when the
circuit breaker (`monitoring/circuit_breaker.py`) trips from
HEALTHY/DEGRADED into QUARANTINED, and updated as recovery is attempted.

| Column | Notes |
|---|---|
| `incident_id` | Primary key. |
| `started_at` / `resolved_at` | `resolved_at` is `NULL` until `status` becomes `RESOLVED`. |
| `type` | `'ERROR_RATE'` or `'VOLUME'`. |
| `severity` | `'LOW'` / `'MEDIUM'` / `'HIGH'`, based on how far over the threshold the window was. |
| `error_rate` | The window's error rate (%) that triggered this; `NULL` for a pure volume anomaly with no elevated error rate. |
| `description` | Human-readable explanation, e.g. `error_rate 18.0% exceeded threshold 5.0%`. |
| `status` | `ACTIVE` -> `RECOVERING` -> `RESOLVED` (maps onto the circuit breaker's QUARANTINED/RECOVERING/back-to-HEALTHY states). |
| `window_started_at` / `window_ended_at` / `records_in_window` / `invalid_in_window` | Extra traceability, not required by the spec, but make an incident self-explanatory without cross-referencing logs. |

### Deliberately not built yet

- No `quality_metrics` history table — window metrics are computed and
  printed live by `monitoring/window.py` but not persisted; only
  incidents (the anomalous windows) are. A dedicated metrics-history table
  is a natural future addition once a dashboard needs to chart trends over
  time rather than just see current state.
