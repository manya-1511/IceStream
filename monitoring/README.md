# Monitoring: Anomaly Detection, Circuit Breaker, Incidents & Recovery

The Day 3 layer that sits between the quality engine and storage:

```text
Real Data Stream -> Quality Engine -> Anomaly Detection ->
    Normal Database OR Quarantine -> Recovery
```

See [`docs/ANOMALY_DETECTION.md`](../docs/ANOMALY_DETECTION.md) for the
full design reasoning. Short version, per file:

- `window.py` — `WindowTracker`: groups records into time windows (default
  10s) and computes each window's total/invalid/error-rate/quality-score/
  records-per-sec. Pure, no DB.
- `anomaly.py` — two threshold-based detectors: `detect_error_rate_anomaly`
  (error rate over a configurable %) and `detect_volume_anomaly` (records/sec
  over a multiple of the recent baseline). Pure functions, no ML.
- `circuit_breaker.py` — `CircuitBreaker`: the
  `HEALTHY -> DEGRADED -> QUARANTINED -> RECOVERING -> HEALTHY` state
  machine. Pure — no DB, no I/O — which is what makes every transition
  testable in isolation (`tests/test_circuit_breaker.py`).
- `incidents_db.py` — reads/writes the `incidents` table.
- `recovery.py` — re-reads records held only because the circuit was open
  from the real dataset on disk, re-validates them, and promotes the ones
  that pass into `valid_orders`.
- `pipeline.py` — `MonitoredPipeline`: wires all of the above together with
  the Day 2 quality engine and storage. Used by both
  `streaming/run_monitored_stream.py` and `scripts/demo_incident.py`.

## Try it

```bash
python streaming/run_monitored_stream.py --rate 10 --window-seconds 10
python scripts/demo_incident.py   # controlled incident + recovery demo
```
