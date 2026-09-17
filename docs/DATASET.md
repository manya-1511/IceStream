# Dataset

## Chosen dataset: Online Retail II

| | |
|---|---|
| **Name** | Online Retail II |
| **Source** | UCI Machine Learning Repository |
| **URL (dataset page)** | https://archive.ics.uci.edu/dataset/502/online+retail+ii |
| **URL (direct download, used by `scripts/download_dataset.py`)** | https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip |
| **License** | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| **Citation** | Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D |
| **Records** | ~1,067,371 transaction line items (two Excel sheets: "Year 2009-2010" and "Year 2010-2011") |
| **Format** | Single `.xlsx` file with two sheets |

This is **real, publicly documented transactional data**, not a synthetic or
generated dataset. It has been used in numerous peer-reviewed papers on
retail analytics and customer segmentation.

## Why this dataset fits IceStream

- **Real transactions**: all rows are real invoices from a UK-based online
  gift retailer, collected between 1 Dec 2009 and 9 Dec 2011.
- **Timestamps**: every row has an `InvoiceDate` (date + time), which is
  exactly what's needed to replay the data in time order as a "real-time"
  stream.
- **Orders**: rows are grouped by `InvoiceNo` (an invoice number =
  effectively one order; multiple rows share the same invoice for
  multi-item orders).
- **Product information**: `StockCode` + `Description` identify the product.
- **Prices & quantities**: `Price` (unit price) and `Quantity` are present
  on every row, which lets a data-quality engine check for negative
  quantities, zero/negative prices, and unusually large orders.
- **Customer information**: `Customer ID` is present for most rows
  (registered customers); it is legitimately missing for some rows (guest /
  unidentified transactions), which is itself a realistic data-quality
  scenario worth detecting rather than hiding.
- **Volume**: over one million rows is enough to make streaming replay and
  aggregate quality metrics meaningful, while still being small enough to
  fit comfortably on a laptop with PostgreSQL.
- **Known, real-world messiness**: this dataset genuinely contains
  cancellations, missing customer IDs, and occasional negative
  prices/quantities. That messiness is a *feature* for a data-quality
  observability project — we get real anomalies to detect, not ones we
  invented ourselves.

## Original columns

| Column | Type | Notes |
|---|---|---|
| `Invoice` | string (nominal) | 6-digit invoice number. Prefixed with `C` for cancellations. |
| `StockCode` | string (nominal) | 5-digit product code. |
| `Description` | string | Product name. Sometimes missing. |
| `Quantity` | integer | Can be negative (cancellations/returns). |
| `InvoiceDate` | datetime | Date and time of the transaction. |
| `Price` | decimal | Unit price in GBP (£). Occasionally 0 (promotional items) or negative (adjustment entries in the source data). |
| `Customer ID` | integer, nullable | Missing for a meaningful share of rows — kept as `NULL`, not invented. |
| `Country` | string | Customer's country. |

## How we use it

`scripts/download_dataset.py` downloads the official ZIP and extracts it
into `data/raw/`, unmodified.

`scripts/preprocess_data.py` reads both sheets, renames columns to our
schema (see `docs/DATABASE_SCHEMA.md`), rejects rows that are structurally
broken (see below), and logs every change it makes. It never silently
drops or invents data.

Rows are **rejected** (written to `data/processed/rejected_rows.csv` with a
reason, not deleted from disk) only when a field required for the pipeline
to function is missing or invalid:

- missing `StockCode`
- missing `Invoice`
- missing/invalid `InvoiceDate`
- non-numeric `Quantity`
- non-numeric `Price`

Rows are **cleaned in place** (kept, but modified) for cosmetic issues:

- leading/trailing whitespace trimmed
- missing `Description` filled with `"UNKNOWN DESCRIPTION"`
- missing `Country` filled with `"UNKNOWN"`
- missing `Customer ID` left as `NULL` (not invented)

Every one of these actions is counted and written to
`data/processed/preprocessing_log.txt` when you run the script.
