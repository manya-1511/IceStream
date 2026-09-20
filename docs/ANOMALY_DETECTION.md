# Anomaly Detection, Circuit Breaker & Recovery — Day 3

This documents how Day 3 extends the Day 2 pipeline:

```text
Real Data Stream -> Quality Engine -> Anomaly Detection ->
    Normal Database OR Quarantine -> Recovery
```

Everything here is intentionally simple enough to explain end-to-end in an
interview: no machine learning, no background threads, no distributed
state — just counters, percentage thresholds, and a small state machine.

## Where the code lives

| Module | Responsibility |
|---|---|
| `monitoring/window.py` | Accumulates records into a time window (default 10s) and computes its metrics. Pure, no DB. |
| `monitoring/anomaly.py` | Two threshold-based detectors: error-rate and volume. Pure functions. |
| `monitoring/circuit_breaker.py` | The `HEALTHY -> DEGRADED -> QUARANTINED -> RECOVERING -> HEALTHY` state machine. Pure — no DB, no I/O. This is what's unit-tested in `tests/test_circuit_breaker.py`. |
| `monitoring/incidents_db.py` | Reads/writes the `incidents` table. |
| `monitoring/recovery.py` | Re-reads affected records from the real dataset and re-validates them. |
| `monitoring/pipeline.py` | `MonitoredPipeline` — wires the above together with the Day 2 quality engine and storage. Used by both `streaming/run_monitored_stream.py` and `scripts/demo_incident.py`. |

Day 2's `streaming/run_stream.py` is untouched and still works exactly as
it did — it has no anomaly detection. `streaming/run_monitored_stream.py`
is a new, separate entrypoint that adds the Day 3 layer on top of the same
reader/validator/quality engine.

## 1. Window-based monitoring

`WindowTracker` accumulates `(is_valid: bool)` per record and closes a
window after `window_seconds` (default 10, configurable via
`--window-seconds`). Closing a window produces a `WindowMetrics` snapshot:
total records, invalid records, valid records, error rate, quality score,
and records/sec. This is arithmetic, not statistics — deliberately, so
it's easy to reason about and to explain.

## 2. Anomaly detection

### Error-rate anomaly

```text
if error_rate > threshold (default 5%):
    trigger an incident
```

`--error-threshold` makes this configurable. Severity scales with how far
over the threshold the window is:

| Condition | Severity |
|---|---|
| `error_rate >= 4x threshold` | HIGH |
| `error_rate >= 2x threshold` | MEDIUM |
| otherwise (still over threshold) | LOW |

### Volume anomaly

```text
if records_per_sec > multiplier x (average of the last few windows):
    trigger an incident
```

`--volume-multiplier` (default 3.0) makes the multiplier configurable.
The detector requires at least `min_baseline_windows` (default 3) prior
*normal* windows before it will fire at all — otherwise the very first
window would have no baseline to compare against and could trigger a false
positive. Windows where an anomaly was detected are excluded from the
baseline history, so one bad window doesn't drag the baseline up and mask
the next one.

No machine learning is used — a moving average and a fixed multiplier are
genuinely sufficient to catch "traffic just jumped 5x for no reason," and
are far easier to explain and debug than a learned model would be.
See `tests/test_anomaly.py` for both detectors' behavior, including the
severity scaling and the "not enough history yet" case.

## 3. The `incidents` table

See `database/incidents_schema.sql` for the full definition. Columns match
the spec (`incident_id`, `started_at`, `resolved_at`, `type`, `severity`,
`error_rate`, `description`, `status`), plus a few extra traceability
columns (which window triggered it, and its record counts) so an incident
is understandable without cross-referencing logs.

`status` is one of `ACTIVE`, `RECOVERING`, `RESOLVED` — this maps directly
onto the circuit breaker's non-healthy states (see below).

## 4. The circuit breaker

```text
HEALTHY -> DEGRADED -> QUARANTINED -> RECOVERING -> HEALTHY
```

`CircuitBreaker` (in `monitoring/circuit_breaker.py`) is a **pure state
machine** — it holds no database connection and performs no I/O. It's
given a window's metrics and returns a `Transition` describing what
changed and what the caller should do about it (open an incident, attempt
recovery, mark one resolved). This separation is what makes
`tests/test_circuit_breaker.py` able to test every transition without a
database at all.

State meanings:

| State | Storage behavior |
|---|---|
| `HEALTHY` | Records stored exactly as the quality engine decides: valid -> `valid_orders`, invalid -> `quarantine_orders`. |
| `DEGRADED` | Same storage behavior as `HEALTHY`. This is a "watch" state — some invalid records this window, but not over the anomaly threshold. No incident is created yet. |
| `QUARANTINED` | The circuit is "open": **every** record — valid or not — is held in `quarantine_orders`. A record that individually passes every quality rule is tagged `rule_triggered = 'CIRCUIT_OPEN'` rather than a real rule name, so it's clearly distinguishable from a genuinely bad record. |
| `RECOVERING` | One full window has now passed while `QUARANTINED`, so an automatic recovery attempt runs (see below). |

Transition logic, evaluated once per closed window:

- **HEALTHY/DEGRADED**: check for a new anomaly (error-rate or volume). If
  found: open the circuit (`QUARANTINED`) and signal that a new incident
  row should be created. Otherwise: `DEGRADED` if this window had any
  invalid records at all, else `HEALTHY`.
- **QUARANTINED**: a full window has now passed with the circuit open ->
  move to `RECOVERING` and signal that a recovery attempt should run now.
- **RECOVERING**: not touched by window evaluation — see
  `record_recovery_result()` below.

## 5. Recovery

```text
source dataset -> re-read affected records -> validate -> process again
```

`monitoring/recovery.py`'s `attempt_recovery()`:

1. Finds every row in `quarantine_orders` tagged `CIRCUIT_OPEN` — these
   are exactly the records that were individually fine but held back
   purely because the circuit was open.
2. Re-reads those exact records **from the real dataset on disk**
   (`data/processed/orders_clean.csv`), matched by their natural key
   (invoice + product + timestamp) — not from IceStream's own quarantine
   copy, so a corrupted copy in our own database can't fool recovery into
   thinking it's fine.
3. Re-runs `validate_record()` and the *same* `QualityEngine` instance's
   `check()` on each one.
4. If it passes: move it into `valid_orders` and delete the quarantine
   row. If it still fails (a rare edge case — e.g. it became a duplicate
   of something stored in the meantime): leave it in quarantine, but
   relabel it with the real rule/reason, since it's no longer just
   "waiting," it's genuinely invalid.
5. If **nothing** is still failing, recovery succeeds:
   `RECOVERING -> HEALTHY`, and the incident is marked `RESOLVED`. If
   something is still failing, the circuit goes back to `QUARANTINED` and
   will try again after the next window.

**This is explicitly a local, educational demonstration of self-healing,
not an enterprise-grade recovery system.** A single pass with no
retry-with-backoff, no external queue, and no distributed coordination is
enough at this project's scale (a single process, a dataset that fits on a
laptop) — but it would not be the right design for a production system
processing a live, unbounded stream. That trade-off is deliberate and
documented here rather than hidden.

### A subtle bug this design surfaced (and fixed)

While building and testing recovery against real data, re-checking a
`CIRCUIT_OPEN` record against the *same* `QualityEngine` instance that
originally saw it produced a false "duplicate" — because `check()`
previously marked a record's key as "seen" the moment it passed, even
though Day 3 can defer actually storing it. Re-checking the same record
later during recovery looked like a duplicate of itself.

Fixed by splitting `QualityEngine.check()` (now read-only) from a new
explicit `QualityEngine.mark_seen()`, which callers invoke only once a
record is actually written to `valid_orders`. This is also a more correct
model in general: a key should be "seen" once it's actually persisted, not
merely once evaluated. `streaming/run_stream.py`, `monitoring/pipeline.py`,
and `monitoring/recovery.py` were all updated to call `mark_seen()`
immediately after `store_valid()`; see `tests/test_quality.py`'s
`test_check_alone_does_not_mark_a_record_as_seen` for the regression test
this added.

## 6. The controlled demonstration

`scripts/demo_incident.py` runs the exact scenario from the spec, against
real data:

```text
Normal stream (real records)
    -> Inject controlled NULL values into unit_price on a fraction
       of the NEXT batch of real records
    -> Error rate crosses the configured threshold
    -> Incident created, circuit -> QUARANTINED
    -> Further real records held in quarantine (CIRCUIT_OPEN)
    -> Normal (uncorrupted) real records resume
    -> Automatic recovery re-reads the held records from the real
       dataset on disk, finds them genuinely valid
    -> RECOVERING -> HEALTHY, incident RESOLVED
```

Every business record streamed is real — sourced from
`data/processed/orders_clean.csv`. The only synthetic element is the
injected `NULL`, applied to an **in-memory copy** of a small number of real
rows; the source CSV on disk is never modified, which is exactly what lets
recovery re-read the correct original value afterwards. This matches the
spec's explicit instruction to inject a controlled fault into real records
for demonstration purposes — it is not a fabricated dataset.

Run it with `python scripts/demo_incident.py` — see `docs/SETUP.md` for
the full walkthrough and what to expect in the output.
