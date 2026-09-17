# Setup — Day 1

These steps get you from a fresh clone to: real data downloaded, cleaned,
loaded into PostgreSQL, and a working `/health` API endpoint.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for PostgreSQL)
- ~200 MB free disk space for the dataset

## 1. Clone and enter the project

```bash
cd icestream
```

## 2. Create your environment file

```bash
cp .env.example .env
```

The defaults work fine for local development — no need to edit anything yet.

## 3. Start PostgreSQL

```bash
docker compose up -d
```

This starts a `postgres:16` container and automatically applies
`database/schema.sql` on first startup (via Postgres's
`docker-entrypoint-initdb.d` mechanism).

Verify it's healthy:

```bash
docker compose ps
```

You should see `icestream_postgres` with status `healthy` (may take a few
seconds after starting).

## 4. Create a Python virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

## 5. Download the real dataset

```bash
python scripts/download_dataset.py
```

This downloads the official "Online Retail II" ZIP from the UCI Machine
Learning Repository into `data/raw/`. See `docs/DATASET.md` for full
details and the license.

> If your network blocks `archive.ics.uci.edu`, download the ZIP manually
> from https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip
> and extract it into `data/raw/` yourself.

## 6. Clean and map the data

```bash
python scripts/preprocess_data.py
```

This reads `data/raw/*.xlsx`, cleans it, and writes:

- `data/processed/orders_clean.csv` — the cleaned data
- `data/processed/rejected_rows.csv` — rows that couldn't be used, with a reason
- `data/processed/preprocessing_log.txt` — a summary of everything that was changed

Read the log — it tells you exactly what happened to the data.

## 7. Load the cleaned data into PostgreSQL

```bash
python scripts/load_to_db.py
```

This inserts every row from `orders_clean.csv` into the `orders` table.
Expect this to take roughly a minute for ~1M rows.

Verify it worked:

```bash
docker compose exec db psql -U icestream -d icestream -c "SELECT COUNT(*) FROM orders;"
```

## 8. Run the backend API

```bash
cd backend
uvicorn main:app --reload --port 8000
```

## 9. Verify Day 1 is working

In another terminal:

```bash
curl http://localhost:8000/health
```

Expected output:

```json
{"status":"healthy"}
```

Also open http://localhost:8000/docs in a browser — you should see the
auto-generated FastAPI docs (Swagger UI) with the `/health` endpoint listed.

## 10. Run the tests

```bash
# from the project root, with the virtualenv active
pytest tests/ -v
```

All 3 tests in `tests/test_health.py` should pass.

## Troubleshooting

- **`psycopg2` fails to install**: make sure you're using
  `psycopg2-binary` (already in `requirements.txt`) — no system Postgres
  headers needed.
- **`docker compose up` fails with a port conflict**: something else is
  using port 5432. Either stop it, or change `DB_PORT` in `.env` and
  re-run `docker compose up -d`.
- **`ModuleNotFoundError: No module named 'config'`**: run `uvicorn` from
  inside the `backend/` directory (step 8), not the project root.
