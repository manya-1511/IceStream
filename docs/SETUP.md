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

All tests in `tests/test_health.py` (Day 1) and `tests/test_quality.py`
(Day 2) should pass — 11 total.

## Day 2: streaming + data quality

### 11. Apply the Day 2 schema

```bash
psql -U icestream -d icestream -h localhost -f database/quality_schema.sql
```

(If you used `docker compose up -d`, this already ran automatically —
`docker-compose.yml` mounts `schema.sql`, `quality_schema.sql`, and
`incidents_schema.sql` as init scripts. This manual step is only needed if
you set up Postgres yourself, per the no-Docker instructions above, *after*
Day 1.)

Verify:

```bash
psql -U icestream -d icestream -h localhost -c "\dt"
```

You should see `orders`, `valid_orders`, and `quarantine_orders`.

### 12. Run the streaming engine

Start small — this streams real records at ~10/sec and stops after 50, so
it takes about 5 seconds:

```bash
python streaming/run_stream.py --rate 10 --limit 50
```

You should see, per record:

```text
[STREAM] Record received | invoice=536365 stock=85123A qty=6 price=2.55
[QUALITY] Passed
[DATABASE] Stored -> valid_orders
```

...ending with a metrics summary:

```text
===== Quality Metrics =====
Total records   : 50
Valid records   : 50 (or fewer, if a real anomaly was in this slice)
Invalid records : 0
Error rate      : 0.0%
Quality score   : 100.0%
============================
```

Try the other rates named in the spec:

```bash
python streaming/run_stream.py --rate 50 --limit 500
python streaming/run_stream.py --rate 100 --limit 1000
```

To replay the *entire* real dataset (~540k+ rows) at a sustainable rate,
drop `--limit`: `python streaming/run_stream.py --rate 100` (this will run
for a while — that's expected, it's over half a million real records).

### 13. Verify records actually entered PostgreSQL

```bash
psql -U icestream -d icestream -h localhost -c "SELECT COUNT(*) FROM valid_orders;"
psql -U icestream -d icestream -h localhost -c "SELECT COUNT(*) FROM quarantine_orders;"
psql -U icestream -d icestream -h localhost -c "SELECT invoice_no, stock_code, rule_triggered, reason FROM quarantine_orders LIMIT 5;"
```

The counts should match what `run_stream.py` printed. If you streamed the
whole dataset, `quarantine_orders` should contain real anomalies —
including the two documented "bad debt adjustment" rows and any duplicate
line items encountered (see `docs/QUALITY_RULES.md`).

### 14. Run the Day 2 tests

```bash
pytest tests/test_quality.py -v
```

All 9 tests should pass — they cover a valid record, a missing required
field, an invalid price, an invalid quantity, a real cancellation (which
must NOT be flagged), a duplicate line item, a check-without-storing edge
case, a future timestamp, and a zero quantity.

## Day 3: anomaly detection + self-healing

### 15. Apply the Day 3 schema

```bash
psql -U icestream -d icestream -h localhost -f database/incidents_schema.sql
```

(Already applied automatically if you used `docker compose up -d` — see
the note in step 11.)

Verify:

```bash
psql -U icestream -d icestream -h localhost -c "\dt"
```

You should now see `orders`, `valid_orders`, `quarantine_orders`, and
`incidents`.

### 16. Run the controlled incident demonstration

This is the fastest way to see everything from Day 3 working together —
it streams real records, injects a controlled fault, watches an incident
get created, and watches the pipeline recover, all in about 5 seconds:

```bash
python scripts/demo_incident.py
```

Expect output like:

```text
[DEMO] Phase 1: 60 real records, streamed normally
[DEMO] Phase 2: 60 real records, 24 with unit_price forced to NULL
[DEMO] Phase 3: 90 real records, streamed normally (recovery should happen here)
...
[WINDOW] 140 records | 24 invalid | error_rate=17.14% | quality_score=82.86% | rate=46.49/s
[CIRCUIT] HEALTHY -> QUARANTINED
[INCIDENT] #1 opened | type=ERROR_RATE severity=MEDIUM | error_rate 17.14% exceeded threshold 5.0%...
...
[WINDOW] 70 records | 0 invalid | error_rate=0.0% | quality_score=100.0% | rate=45.51/s
[CIRCUIT] QUARANTINED -> RECOVERING
[RECOVERY] Attempting recovery: re-reading affected records from the source dataset...
[RECOVERY] attempted=70 recovered=70 still_failing=0 success=True
[CIRCUIT] RECOVERING -> HEALTHY
[INCIDENT] #1 RESOLVED

===== DEMO SUMMARY =====
...
[DEMO] SUCCESS: an incident was detected, the circuit opened, and the pipeline recovered to HEALTHY.
```

Then verify the incident directly in Postgres:

```bash
psql -U icestream -d icestream -h localhost -c "SELECT incident_id, type, severity, status, error_rate, started_at, resolved_at FROM incidents;"
psql -U icestream -d icestream -h localhost -c "SELECT rule_triggered, COUNT(*) FROM quarantine_orders GROUP BY rule_triggered;"
```

You should see one `RESOLVED` incident, and `quarantine_orders` containing
only the genuinely-corrupted rows (`rule_unit_price_required`) — no
`CIRCUIT_OPEN` rows should remain, since recovery moved all of those into
`valid_orders`.

The demo is deterministic and safe to re-run — it truncates
`valid_orders`, `quarantine_orders`, and `incidents` at the start of every
run, and never modifies `data/processed/orders_clean.csv`.

### 17. Run the normal monitored stream (no injected faults)

```bash
python streaming/run_monitored_stream.py --rate 10 --window-seconds 10
```

Against unmodified real data, this should stay `HEALTHY` the whole time —
confirms the anomaly detectors don't produce false positives on clean data.

### 18. Run the Day 3 tests

```bash
pytest tests/test_window.py tests/test_anomaly.py tests/test_circuit_breaker.py -v
```

31 tests should pass, covering: window metric calculation; both anomaly
detectors (including severity scaling and "not enough history yet"); and
every circuit breaker transition (`HEALTHY -> DEGRADED`,
`DEGRADED -> HEALTHY`, `HEALTHY/DEGRADED -> QUARANTINED` for both an
error-rate and a volume anomaly, `QUARANTINED -> RECOVERING`,
`RECOVERING -> HEALTHY`, and `RECOVERING -> QUARANTINED` on a failed
recovery attempt).

Run the complete suite (Day 1 + 2 + 3):

```bash
pytest tests/ -v
```

35 tests total should pass.

## Troubleshooting

- **`psycopg2` fails to install**: make sure you're using
  `psycopg2-binary` (already in `requirements.txt`) — no system Postgres
  headers needed.
- **`docker compose up` fails with a port conflict**: something else is
  using port 5432. Either stop it, or change `DB_PORT` in `.env` and
  re-run `docker compose up -d`.
- **`ModuleNotFoundError: No module named 'config'`**: run `uvicorn` from
  inside the `backend/` directory (step 8), not the project root.
