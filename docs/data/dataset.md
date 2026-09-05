# IceStream — Dataset Documentation (Day 2)

## 1. Dataset choice

**Brazilian E-Commerce Public Dataset by Olist**
Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
License: CC BY-NC-SA 4.0 (non-commercial use — fine for a portfolio project;
not for resale)

### Why this dataset

IceStream needs real order/checkout data with customers, order line items,
and payment events. Olist fits all four requirements from the brief:

| Requirement | Covered by |
|---|---|
| e-commerce transactions | `olist_order_items_dataset.csv` |
| orders | `olist_orders_dataset.csv` |
| customers | `olist_customers_dataset.csv` |
| payments / checkout-like events | `olist_order_payments_dataset.csv` |

It's real, anonymized commercial data (~100k orders, 2016–2018, multiple
Brazilian marketplaces sold through Olist), it's free and legitimately
public on Kaggle, it's widely used (so any modeling choices here are
checkable against prior work), and its multi-table structure (orders,
items, payments, customers, products, sellers) is exactly the kind of
join-heavy real-world messiness a data-quality/observability project
should be built against — much more realistic than a single flat CSV of
synthetic transactions.

### Alternatives considered

- **UCI Online Retail II** — single UK gift-retailer, no separate
  payments table, no customer geography beyond country. Weaker fit for
  a payments-aware checkout schema.
- **Instacart Market Basket** — no prices, no payments, US grocery
  reorders only — good for basket analysis, not for a checkout/payment
  pipeline.
- **Kaggle "Fraud E-Commerce" / synthetic transaction datasets** —
  explicitly synthetic; the brief asked for real transactions.

Olist was the clear best fit and is the same choice already recorded in
this project's plan.

## 2. Raw tables used

| File | Rows (full dataset) | Used for |
|---|---|---|
| `olist_orders_dataset.csv` | 99,441 | order_id, customer_id, order_status, purchase timestamp |
| `olist_order_items_dataset.csv` | 112,650 | product_id, seller_id, price, freight_value |
| `olist_order_payments_dataset.csv` | 103,886 | payment_type (payment_method) |
| `olist_customers_dataset.csv` | 99,441 | customer_state, customer_city |
| `olist_products_dataset.csv` | 32,951 | product_category_name |
| `product_category_name_translation.csv` | 71 | Portuguese → English category names |

Row counts above are the full Kaggle dataset's, as documented by Olist and
widely reported by public analyses of it — **not** counts from anything
downloaded in this environment (see §5, Acquisition).

Not used in Day 2 (reserved for later days): `olist_sellers_dataset.csv`,
`olist_order_reviews_dataset.csv`, `olist_geolocation_dataset.csv`.

## 3. Canonical field mapping

This is the authoritative mapping from Olist source columns to the
IceStream canonical `CheckoutEvent` (`etl/schemas.py`). Every field is
one of: a **real** source column, a **derived** value computed from real
columns via documented logic, or a **constant/None** for something the
dataset genuinely does not provide.

| Canonical field | Type | Origin | Notes |
|---|---|---|---|
| `transaction_id` | `str` (UUID5) | **Derived** | `uuid5(ICESTREAM_NAMESPACE, f"{order_id}:{product_id}")`. Deterministic and reproducible — the same source row always yields the same id. Olist has no line-item transaction id of its own. |
| `order_id` | `str` | **Real** | `orders.order_id` |
| `customer_id` | `str` | **Real** | `orders.customer_id`. **Important quirk**: in the real Olist dataset, `customer_id` is *order-scoped* — the same physical person gets a new `customer_id` on every order. Olist's `customer_unique_id` is the actual repeat-customer key but is not part of the canonical schema today (not requested by the brief; can be added later if repeat-customer analysis is needed). |
| `timestamp` | `datetime` | **Real** | `orders.order_purchase_timestamp` |
| `product_id` | `str` | **Real** | `order_items.product_id` |
| `quantity` | `int` | **Derived** | Count of `order_items` rows sharing `(order_id, product_id)`. Olist's `order_items` is unit-level (one row per unit), so this is a real aggregation, not an invented number. |
| `unit_price` | `Decimal` | **Real** | `order_items.price` (asserted constant within the aggregated group; the pipeline logs a warning if it ever isn't — see `etl/preprocess.py::aggregate_line_items`) |
| `subtotal` | `Decimal` | **Derived** | `quantity * unit_price`, rounded to 2 dp |
| `tax_amount` | `Decimal \| None` | **Not available** | Brazilian tax is embedded in `price`; Olist never breaks it out. Always `None`. |
| `discount` | `Decimal \| None` | **Not available** | No discount column exists anywhere in the dataset. Always `None`. |
| `shipping_amount` | `Decimal` | **Real** (extra field) | Sum of `order_items.freight_value` across the aggregated group. Olist already allocates freight per item when an order has multiple items, so this sums cleanly. Added beyond the base spec because it's real data that materially affects `total_amount`. |
| `total_amount` | `Decimal` | **Derived** | `subtotal + shipping_amount (+ tax_amount − discount, both currently 0/None)` |
| `currency` | `Literal["BRL"]` | **Constant** | Olist is a Brazil-only marketplace; not a per-record source column, but a documented fact about the dataset. |
| `payment_method` | `str \| None` | **Derived** | `order_payments.payment_type` for the order's *highest-value* payment row. See §4 for why an order can have more than one payment row and how the "primary" one is chosen. Real values: `credit_card`, `boleto`, `voucher`, `debit_card`, `not_defined`. |
| `country` | `Literal["BR"]` | **Constant** | Olist operates only in Brazil. Not a per-record column. |
| `device_type` | `Literal["web","mobile","app"] \| None` | **Not available** | No session/device tracking exists in this dataset at all. Always `None` for Day 2. If ever added, it would have to be a clearly-labeled synthetic augmentation on a future day — never silently invented. |
| `order_status` | `str` | **Real** (extra field) | `orders.order_status` (e.g. `delivered`, `shipped`, `canceled`, `invoiced`). A checkout event happens at purchase time, so this is carried as context, not used to filter out orders (a canceled order still produced a real checkout event). |
| `customer_state` | `str \| None` | **Real** (extra field) | `customers.customer_state` |
| `customer_city` | `str \| None` | **Real** (extra field) | `customers.customer_city` |
| `product_category` | `str \| None` | **Real** (extra field) | `products.product_category_name`, translated to English via `product_category_name_translation.csv` where a translation exists, else the original Portuguese name, else `None` if the product isn't in `products.csv` at all. |
| `seller_id` | `str \| None` | **Real** (extra field) | `order_items.seller_id` (first seller in the aggregated group) |

### Fields requested in the brief that are *not* separately present

The brief's example schema listed `tax_amount`, `discount`, and
`device_type`. All three are kept in the canonical schema (so downstream
consumers have a stable shape to code against) but are always `None` for
data sourced from Olist, exactly as described above — no field was
invented to fill a gap.

## 4. Key preprocessing decisions

### 4.1 Quantity aggregation

Olist's `order_items` table is **unit-level**: a customer buying 2 units
of the same product in one order produces 2 rows with the same
`(order_id, product_id)`, same `price`, and sequential `order_item_id`.
The pipeline groups by `(order_id, product_id)` and sets
`quantity = row count`, `unit_price = mean(price)` (a sanity check logs a
warning if the price wasn't actually constant within the group — it always
is in practice), and `shipping_amount = sum(freight_value)`.

### 4.2 Primary payment method

An order can have **multiple** payment rows — e.g. part paid by voucher
and the rest by credit card, or several installment charges. Since the
canonical schema has one `payment_method` field per event, the pipeline
picks the payment row with the **largest `payment_value`** as the
"primary" method (ties broken by `payment_sequential`). This represents
what the customer *mostly* paid with. See
`etl/preprocess.py::resolve_primary_payment`.

### 4.3 Orders without a matching order-items row, or vice versa

The join between orders and aggregated line items is an **inner join** —
an order-item row without a matching order (or an order with zero items)
produces no event, since a checkout event fundamentally requires both.

### 4.4 Non-delivered orders are still included

`order_status` is carried as context, not used as a filter. A `canceled`
or `invoiced` order still represents a real checkout event that happened
at `order_purchase_timestamp` — filtering those out would misrepresent
the actual purchase funnel, which is exactly the kind of signal a
data-quality/observability platform should be able to see.

## 5. Acquisition

### Real dataset (required for anything beyond unit tests)

```bash
pip install kaggle --break-system-packages
# One-time: place your Kaggle API token at ~/.kaggle/kaggle.json
# (see https://www.kaggle.com/settings/account -> "Create New Token")
bash scripts/download_dataset.sh
```

This downloads and unzips the dataset into `data/raw/olist/`. See
`scripts/download_dataset.sh` for the exact `kaggle datasets download`
command and `data/raw/README.md` for the expected file layout.

> **Note on this environment**: the dataset was *not* downloaded as part
> of building this Day 2 pipeline, because Kaggle requires a personal API
> token and this development environment's network access does not
> include `kaggle.com`. Everything in `etl/` was built and verified
> end-to-end against the fixture described below instead. Run the command
> above on your own machine to pull the real ~100k-order dataset, then
> point the pipeline at it (§6).

### Fixture dataset (used for development and tests in this repo)

`data/samples/olist_raw_fixture/` contains 15 hand-authored orders using
the exact real column names and value conventions described above (not
randomly generated — every value was written by hand so pipeline output
is fully predictable). It exists so `etl/` can be developed, tested, and
CI-checked without needing Kaggle credentials or a ~100MB download. See
`data/samples/olist_raw_fixture/README.md` for exactly what it contains
and why.

**Never treat the fixture as a stand-in for real analysis** — it has 15
orders, not ~100k, and was constructed by hand to exercise specific code
paths (quantity aggregation, multi-payment orders, missing category
translations), not to represent Olist's actual data distribution.

## 6. Running the pipeline

```bash
# Install etl dependencies (separate from the FastAPI backend's requirements)
pip install -r etl/requirements.txt --break-system-packages

# Against the fixture (default — no download needed):
python -m etl.preprocess
python -m etl.validate
python -m etl.to_events

# Against the real downloaded dataset:
python -m etl.preprocess --raw-dir data/raw/olist
python -m etl.validate --input data/processed/checkout_events.parquet
python -m etl.to_events --input data/processed/checkout_events.parquet
```

### Expected output (fixture dataset, verified in this repo)

```
$ python -m etl.preprocess
INFO Loading raw tables from data/samples/olist_raw_fixture
INFO Building canonical frame
INFO Built 17 candidate record(s) before schema validation
INFO Wrote 17 record(s) to data/processed/checkout_events.parquet and data/processed/checkout_events.csv
INFO Preprocessing complete: 17 valid / 17 total candidate record(s)

$ python -m etl.validate
INFO Validating 17 record(s) from data/processed/checkout_events.parquet
INFO Schema validation: 17/17 valid (0.00% error rate)
INFO Uniqueness: OK — no duplicate transaction_id
INFO Referential completeness: OK — order_id/customer_id/product_id all populated
INFO Timestamp range: OK — all within known Olist collection window
INFO Price sanity: OK — all prices within plausible BRL range
INFO Overall result: PASS

$ python -m etl.to_events
INFO Loaded 17 processed record(s) from data/processed/checkout_events.parquet
INFO Wrote 17 streaming-ready event(s) to data/processed/events/checkout_events.jsonl
```

21 raw `order_items` rows collapse into 17 canonical events because three
orders (`ord_0001`, `ord_0007`, `ord_0013`) each have 2–3 rows of the same
product, which aggregate into a single event with `quantity > 1`.

### Expected output shape (real dataset, not run in this environment)

Running the same commands with `--raw-dir data/raw/olist` against the
full download should produce on the order of ~98,000–99,000 canonical
events (slightly fewer than the ~112,650 raw `order_items` rows, both
because of the same-product aggregation described above and because a
small number of rows fail the cleaning step in §4.3 or the schema's
positive-price / non-null checks). Exact counts will depend on the
download's state as of whenever you run it — verify with the `validate`
report rather than trusting this estimate.

## 7. Tests

```bash
python -m pytest etl/tests/ -v
```

34 tests, all passing against the fixture dataset: schema validation
(valid/invalid cases, cross-field consistency), preprocessing (row
counts, quantity aggregation, primary-payment selection, category
translation + fallback, sort order, constant fields, null-field
guarantees), the validation CLI's individual checks, and the JSONL event
conversion (line count, sort order, per-line schema validity, id
uniqueness).

## 8. What Day 2 explicitly does not do

Per scope: **no Kafka**. `etl/to_events.py` produces an ordered JSON Lines
file — the exact shape a future replay engine will read and publish — but
nothing here connects to Kafka, and no topic is touched. That's Day 3+.
