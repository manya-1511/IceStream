# Streaming Engine

Replays the real processed dataset (`data/processed/orders_clean.csv`) as a
simulated real-time order stream: rows are read in their original
`invoice_date` order and emitted at an approximate target rate.

## Files

- `reader.py` — reads the real CSV, sorted by `invoice_date`. Forces
  `invoice_no`/`stock_code` to string dtype (they're IDs, not numbers —
  see the note in the file for why this matters).
- `validator.py` — the "receive → validate" step: coerces a raw row into
  typed Python values, separately from whether those values are
  *business*-valid (that's the quality engine's job).
- `db.py` — stores records into `valid_orders` / `quarantine_orders`,
  and preloads existing duplicate-detection keys on startup so restarting
  the stream doesn't forget what it already saw.
- `run_stream.py` — the CLI entrypoint. See usage below.

## Usage

```bash
python streaming/run_stream.py --rate 10
python streaming/run_stream.py --rate 50 --limit 2000
python streaming/run_stream.py --rate 100 --truncate
```

| Flag | Meaning |
|---|---|
| `--rate` | Approximate records/sec to emit (default 10). |
| `--source` | Path to the processed CSV (default `data/processed/orders_clean.csv`). |
| `--limit` | Stop after N records (default: stream everything). Useful for quick tests. |
| `--truncate` | Empty `valid_orders`/`quarantine_orders` before starting. |
| `--quiet` | Only print the final metrics summary, not per-record logs. |

Each record logs:

```text
[STREAM] Record received | invoice=536365 stock=85123A qty=6 price=2.55
[QUALITY] Passed
[DATABASE] Stored -> valid_orders
```

or, for a failing record:

```text
[STREAM] Record received | invoice=A563186 stock=B qty=1 price=-11062.06
[QUALITY] Failed: unit_price is negative (-11062.06) (rule=rule_unit_price_non_negative)
[DATABASE] Stored -> quarantine_orders
```

See [`docs/QUALITY_RULES.md`](../docs/QUALITY_RULES.md) for the quality
engine's rules and [`docs/SETUP.md`](../docs/SETUP.md) for full setup and
verification steps.
