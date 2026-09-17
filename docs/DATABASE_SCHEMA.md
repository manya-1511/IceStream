# Database Schema — Day 1

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
- No `quality_events` / `alerts` table yet — added on the day the quality
  engine is built (Day 3), once we know exactly what shape those events
  need to be.
