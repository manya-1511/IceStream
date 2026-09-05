# `data/raw/` — raw dataset storage

This directory holds the **unmodified** downloaded dataset. Nothing in
here is committed to Git except this file and directory placeholders —
raw data is regenerable via `scripts/download_dataset.sh` and shouldn't
bloat the repository.

## Layout

```
data/raw/
└── olist/                              <- populated by scripts/download_dataset.sh
    ├── olist_orders_dataset.csv
    ├── olist_order_items_dataset.csv
    ├── olist_order_payments_dataset.csv
    ├── olist_customers_dataset.csv
    ├── olist_products_dataset.csv
    ├── olist_sellers_dataset.csv
    ├── olist_order_reviews_dataset.csv
    ├── olist_geolocation_dataset.csv
    └── product_category_name_translation.csv
```

Only the first five files (plus the translation file) are used by the
Day 2 `etl/` pipeline. `olist_sellers_dataset.csv`, the reviews dataset,
and the geolocation dataset are downloaded as part of the same Kaggle
archive but not currently consumed — reserved for future days
(e.g. seller-level lineage, review-driven quality signals).

See [`../../docs/data/dataset.md`](../../docs/data/dataset.md) for the
full source, license, and field-mapping documentation, and
[`../samples/olist_raw_fixture/`](../samples/olist_raw_fixture/) for a
small hand-authored fixture with the same file names/columns that lets
the pipeline run without this real download.
