# Data Quality Engine

A small rule-based engine that checks each streamed order against
completeness, validity, and uniqueness rules, adapted specifically to what
exists in the real dataset (see [`docs/QUALITY_RULES.md`](../docs/QUALITY_RULES.md)
for the full reasoning, with real examples found in the data).

## Files

- `rules.py` — individual rule functions. Each is `(record: dict) -> str | None`:
  returns `None` if the record passes, or a reason string if it fails.
- `engine.py` — `QualityEngine`: runs a record through all rules in order
  (completeness → validity → uniqueness), stopping at the first failure,
  and returns a `QualityResult(valid, reason, rule, timestamp)`.
- `metrics.py` — `compute_metrics(total, valid, invalid)` →
  quality score / error rate.

## Rule categories

| Category | Rules |
|---|---|
| Completeness | `invoice_no`, `unit_price`, `invoice_date` cannot be missing |
| Validity | quantity sign must match the cancellation flag (never zero); `unit_price >= 0`; `invoice_date` not in the future |
| Uniqueness | the same line item (invoice + product + qty + price + timestamp) can't be stored twice |

## Usage

```python
from engine import QualityEngine

engine = QualityEngine()
result = engine.check(record)  # record: dict with the orders table's fields

if result.valid:
    ...  # store into valid_orders
else:
    print(result.rule, result.reason)  # store into quarantine_orders
```

Used by `streaming/run_stream.py`. Tested in `tests/test_quality.py`.
