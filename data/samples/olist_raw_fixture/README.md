# Olist raw fixture — development/test data only

**This is NOT the real Olist dataset.** It is a small, hand-authored set of
15 orders that uses the exact real column names and value conventions of
the "Brazilian E-Commerce Public Dataset by Olist" (Kaggle) so that the
preprocessing, validation, and event-conversion code in `etl/` can be
developed and unit-tested without requiring the full ~1.5M-row download or
Kaggle credentials.

Every value here was written by hand (not randomly generated) so the
expected output of `etl/preprocess.py`, `etl/validate.py`, and
`etl/to_events.py` is fully predictable and reviewable — see
`docs/data/dataset.md` for the exact expected output when run against this
fixture.

To work with the **real** dataset (required for anything beyond unit
tests — e.g. realistic volume, real category distributions, real
seasonality), download it with `scripts/download_dataset.sh` into
`data/raw/olist/` and re-run the same `etl/` scripts pointed at that
directory. See `docs/data/dataset.md` for full instructions.

## Files in this fixture (mirrors the real Kaggle file names)

| File | Rows | Notes |
|---|---|---|
| `olist_orders_dataset.csv` | 15 | Includes `delivered`, `shipped`, `canceled`, `invoiced` statuses and one order with a null delivery date |
| `olist_order_items_dataset.csv` | 21 | Includes 3 orders with 2–3 rows of the *same* product (exercises quantity aggregation) |
| `olist_order_payments_dataset.csv` | 16 | Includes one order (`ord_0007`) with two payment rows of different types (exercises "primary payment method" selection) and one `not_defined` payment type |
| `olist_customers_dataset.csv` | 15 | One customer per order, spread across 10 Brazilian states |
| `olist_products_dataset.csv` | 10 | Real Olist category names (Portuguese) |
| `product_category_name_translation.csv` | 7 | Real Olist category → English translation, intentionally missing `relogios_presentes` to exercise the left-join fallback |
