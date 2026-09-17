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
Python Streaming Engine            (Day 2+) replays rows in timestamp order,
          |                        at a configurable speed, one "order event"
          |                        at a time
          v
Data Quality Engine                (Day 2+) checks each event against rules
          |                        (missing fields, price anomalies, schema
          |                        drift, duplicate invoices, etc.)
          v
PostgreSQL                         orders table (Day 1) + quality tables (later)
          |
          v
FastAPI                            REST endpoints to query orders/quality state
          |
          v
WebSocket                          pushes new events + quality alerts live
          |
          v
React Dashboard                    (Day 2+) shows the stream and quality metrics
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
├── streaming/     Streaming replay engine (Day 2+)
├── quality/       Data quality rule engine (Day 2+)
├── database/      SQL schema
├── tests/         Automated tests
├── scripts/       One-off/operational scripts (download, preprocess, load)
├── docs/          This documentation
├── .env.example   Template for local environment variables
├── docker-compose.yml   PostgreSQL container definition
└── README.md
```

## Day-by-day plan (high level)

- **Day 1** (this doc set): real dataset chosen and downloaded, repo
  scaffolded, Postgres schema + connection, preprocessing script, `/health`.
- **Day 2**: streaming replay engine — read `orders_clean.csv` in
  `invoice_date` order and emit rows at a configurable speed.
- **Day 3**: data quality engine — rule-based checks run against each
  streamed event (nulls, negative prices, quantity outliers, duplicate
  invoices, schema drift, spikes/drops in order volume).
- **Day 4**: FastAPI REST endpoints + WebSocket channel to push
  events/alerts live.
- **Day 5**: React dashboard consuming the WebSocket + REST API.
- **Day 6+**: automated reactions to detected problems (e.g. pausing
  ingestion, flagging orders, alerting), plus tests and polish.

This file will be updated as each day's components are added.
