# IceStream Architecture

## Overview

IceStream replays a **real, historical e-commerce dataset** as if it were a
live order stream, checks each order against a set of data-quality rules in
real time, stores everything in PostgreSQL, and pushes live updates to a
React dashboard over WebSockets.

No fake/synthetic transactions are generated anywhere in this project. The
"streaming" part comes from replaying real historical rows in timestamp
order at a controllable speed — a standard, honest way to simulate
real-time behavior from a static dataset.

## Pipeline

```text
REAL PUBLIC E-COMMERCE DATA        data/raw/*.xlsx (Online Retail II, UCI)
          |
          v
scripts/preprocess_data.py         cleans + maps into our schema
          |
          v
data/processed/orders_clean.csv
          |
          v
Python Streaming Engine            streaming/run_monitored_stream.py replays
          |                        rows in invoice_date order, at a
          |                        configurable --rate (records/sec)
          v
Data Quality Engine                quality/engine.py checks each record
          |                        against completeness, validity, and
          |                        uniqueness rules (see docs/QUALITY_RULES.md)
          v
Anomaly Detection                  monitoring/window.py groups records into
          |                        time windows; monitoring/anomaly.py checks
          |                        each window for an error-rate or volume
          |                        anomaly (see docs/ANOMALY_DETECTION.md)
          v
Normal Database  OR  Quarantine    valid_orders / quarantine_orders, gated by
          |                        monitoring/circuit_breaker.py's state
          v
Recovery                           on a detected anomaly, monitoring/recovery.py
          |                        re-reads affected records from the real
          |                        dataset and re-validates them
          v
PostgreSQL                         orders (Day 1) + valid_orders /
          |                        quarantine_orders (Day 2) + incidents (Day 3)
          v
FastAPI                            REST endpoints to query orders/quality state
          |
          v
WebSocket                          pushes new events + quality alerts live
          |
          v
React Dashboard                    (Day 4+) shows the stream and quality metrics
```

## Why this stack, and why not Kafka/Flink/Spark/Iceberg/Kubernetes

This project is intentionally built on a **simple, understandable stack**:

- **Python** — for both the streaming replay engine and the quality checks.
  A Python generator/loop reading rows in order and sleeping between them is
  a stream; you don't need a message broker to learn streaming *concepts*.
- **PostgreSQL** — one well-understood relational database for both the
  order data and (later) quality/alerting data.
- **FastAPI** — a small, modern Python web framework for REST + WebSocket
  endpoints.
- **WebSockets** — the simplest way to push live updates to a browser
  without polling.
- **React** — the dashboard.

Kafka, Flink, Spark, Iceberg, and Kubernetes solve problems at a scale
(distributed, multi-node, fault-tolerant, high-throughput) that this project
does not have. Adding them here would hide the underlying concepts behind
infrastructure complexity — the opposite of the learning goal.

## Repository layout

```text
icestream/
├── backend/       FastAPI app (Day 1: /health; later: REST + WebSocket API)
├── frontend/       React dashboard (Day 2+)
├── data/
│   ├── raw/       Original downloaded dataset (not committed to git)
│   └── processed/ Cleaned CSV + preprocessing logs (not committed to git)
├── streaming/     Streaming replay engine (Day 2) + monitored variant (Day 3)
├── quality/       Data quality rule engine (Day 2)
├── monitoring/    Anomaly detection, circuit breaker, incidents, recovery (Day 3)
├── database/      SQL schema
├── tests/         Automated tests
├── scripts/       One-off/operational scripts (download, preprocess, load)
├── docs/          This documentation
├── .env.example   Template for local environment variables
├── docker-compose.yml   PostgreSQL container definition
└── README.md
```

## Day-by-day plan (high level)

- **Day 1**: real dataset chosen and downloaded, repo scaffolded, Postgres
  schema + connection, preprocessing script, `/health`.
- **Day 2**: streaming replay engine (`streaming/`) reads `orders_clean.csv`
  in `invoice_date` order and emits records at a configurable `--rate`; each
  one passes through `receive -> validate -> quality check -> store`
  (`quality/`) and lands in `valid_orders` or `quarantine_orders`. See
  [`docs/QUALITY_RULES.md`](QUALITY_RULES.md).
- **Day 3** (done — see [`docs/ANOMALY_DETECTION.md`](ANOMALY_DETECTION.md)):
  records are grouped into time windows (`monitoring/window.py`); each
  window is checked for an error-rate or volume anomaly
  (`monitoring/anomaly.py`); a detected anomaly opens a circuit breaker
  (`monitoring/circuit_breaker.py`) and creates a row in `incidents`; while
  open, records are held in quarantine instead of being trusted; an
  automatic recovery pass (`monitoring/recovery.py`) re-reads and
  re-validates the held records from the real dataset, closing the circuit
  once they check out clean.
- **Day 4**: FastAPI REST endpoints + WebSocket channel to push
  events/alerts/incidents live.
- **Day 5**: React dashboard consuming the WebSocket + REST API.
- **Day 6+**: persisted quality metrics history, tests and polish.

This file will be updated as each day's components are added.
