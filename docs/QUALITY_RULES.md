# Data Quality Rules — Day 2

This documents *why* each rule is shaped the way it is. The generic rule
descriptions in the spec ("quantity > 0", "duplicate ID detection") don't
map onto this dataset literally — real datasets are messier than that, and
adapting the rules to what's actually in the data is the point of this
exercise. Every example below is a real row from the dataset, found while
building this.

## Completeness

| Rule | Field | Why |
|---|---|---|
| `rule_invoice_no_required` | `invoice_no` | Our required order identifier — nothing downstream works without it. |
| `rule_unit_price_required` | `unit_price` | Can't evaluate any price rule, or compute revenue, without it. |
| `rule_invoice_date_required` | `invoice_date` | The entire streaming replay depends on ordering by this field. |

No completeness rule exists for `description`, `customer_id`, or `country`
— Day 1's preprocessing already backfills/accepts missing values for those
(`UNKNOWN DESCRIPTION`, `NULL`, `UNKNOWN` respectively; see
`docs/DATASET.md`), so by the time a record reaches the streaming engine
they're not considered data quality failures.

## Validity

### Quantity: adapted, not literal

The spec's generic rule is "quantity > 0". Applied literally to this
dataset, it would flag **every single legitimate cancellation** as
invalid — UCI's own documentation says an invoice number starting with
`'C'` is a cancellation, and cancellations have negative quantity by
design (e.g. invoice `C536379`, quantity `-1`).

So the real rule (`rule_quantity_sign_matches_cancellation`) is:

- `is_cancelled = True`  → quantity must be **negative**
- `is_cancelled = False` → quantity must be **positive**
- quantity may never be exactly `0` (this never happens in the real data —
  zero-quantity rows don't exist in ~540k+ real records, so if one ever
  showed up it would be a genuine anomaly)

This also catches a real edge case found while testing: the dataset
contains ~1,300 rows with negative quantity where the invoice number does
**not** start with `'C'` (e.g. manual/adjustment entries with invoice
prefixes like `'A'`). Those are correctly flagged as invalid — a data
quality platform's job is to surface exactly this kind of inconsistency
for a human to review, not to quietly explain it away.

### Price: `>= 0`, not `> 0`

`unit_price == 0` is valid — the dataset has 2,515 real rows at price `0`
(promotional / free items), and treating those as errors would quarantine
perfectly normal transactions.

`unit_price < 0` is invalid, and this rule caught a genuine anomaly in the
real dataset during testing:

```
invoice_no=A563186  stock_code=B  description="Adjust bad debt"
quantity=1  unit_price=-11062.06
```

(There's a matching invoice `A563187` with the same values, and a
`A563185` with the *positive* version of the same amount — these are a
real bad-debt adjustment entry in the source data, not something we
invented.)

### Timestamp: not in the future

`rule_invoice_date_not_future` compares `invoice_date` against
`datetime.now()` at check time. Because this dataset is historical
(2009–2011) and we're replaying it in a simulation, this rule should
essentially never fire in practice — it exists as a safety net against a
corrupted or misparsed timestamp, which is exactly the kind of thing a
data quality engine should not assume can't happen.

## Uniqueness: adapted, not literal

The spec's generic rule is "duplicate order/transaction ID detection".
Applied literally to `invoice_no`, this doesn't work: in this dataset an
invoice number is **not** a unique row ID — one invoice legitimately spans
many rows, one per product purchased (e.g. invoice `536365` has 7 line
items, one per product).

The actual thing worth flagging as "duplicate" is a **duplicate line
item**: the exact same invoice + product + quantity + price + timestamp
appearing more than once. That combination should be unique — if it
repeats, it's most likely a duplicate ingestion event, not a second
legitimate purchase of the identical product at the identical instant.

`rule_duplicate_line_item` implements this with a composite key:
`(invoice_no, stock_code, quantity, unit_price, invoice_date)`. This isn't
a hypothetical — the real dataset contains 10,151 rows that are exact
duplicates of another row on this composite key.

**How duplicate memory works**: the engine keeps an in-memory set of every
key it has seen. At startup, `streaming/db.py:preload_seen_keys()` loads
every key already present in `valid_orders`, so restarting the stream
doesn't forget what it already accepted. This was verified directly: a
record is accepted on first run, then correctly rejected as a duplicate if
the exact same stream is replayed against the same database afterwards.

**Known limitation**: the seen-set lives in memory for the life of one
`run_stream.py` process. At this dataset's scale (~540k rows,
low-hundreds-of-MB of keys) this is fine on a laptop; a true production
system at much larger scale would use a database-backed uniqueness
constraint or a windowed/external dedup store instead. Documented here
rather than hidden, per the project's "understand every component" goal.

## What "invalid" produces

Every call to `QualityEngine.check()` returns a `QualityResult`:

```python
@dataclass
class QualityResult:
    valid: bool
    reason: Optional[str]     # human-readable explanation
    rule: Optional[str]       # which rule function failed (None if valid)
    timestamp: datetime       # when the check happened
```

Rules run in a fixed order — completeness, then validity, then uniqueness
— and the engine stops at the **first** failure. So a record with both a
missing field and a bad price is reported with one clear reason (the
completeness one), not two competing ones. This keeps `quarantine_orders`
readable: one row, one rule, one reason.

## A note on rate and throughput

`streaming/run_stream.py --rate N` targets *N* records/sec by sleeping
`max(0, 1/N - processing_time)` between records. Measured on this project's
own test machine against the real dataset:

| Target rate | Measured throughput |
|---|---|
| 10/sec | ~9.5/sec (within ~5%) |
| 50/sec | close to target |
| 100/sec | ~75-80/sec |

At higher rates, the per-record synchronous database commit
(`engine.begin()` per insert) becomes the bottleneck rather than the sleep
interval — the pipeline is correctly rate-limiting, but each insert simply
takes longer than the 10ms budget `--rate 100` allows. This is an
intentional simplicity trade-off (one transaction per record, easy to
reason about) rather than a bug; batching inserts would close the gap but
adds complexity this project doesn't need yet. Documented here rather than
silently under-delivering on the requested rate.
