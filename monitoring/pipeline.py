"""
MonitoredPipeline ties together everything Day 3 adds:

    Real Data Stream -> Quality Engine -> Anomaly Detection ->
        Normal Database OR Quarantine -> Recovery

Per record: validate -> quality check -> circuit-aware storage decision.
Every `window_seconds`: close the window, evaluate the circuit breaker,
open/update/resolve incidents, and run recovery when appropriate.

This class is the shared engine behind both:
  - streaming/run_monitored_stream.py (normal monitored operation)
  - scripts/demo_incident.py (the controlled incident demonstration)
so the two entrypoints don't duplicate this logic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "streaming"))
from validator import validate_record, EMPTY_TYPED_RECORD, raw_to_jsonable  # noqa: E402
import db as streaming_db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from window import WindowTracker  # noqa: E402
from circuit_breaker import CircuitBreaker, Transition  # noqa: E402
import incidents_db  # noqa: E402
import recovery  # noqa: E402


class MonitoredPipeline:
    def __init__(
        self,
        engine,
        quality_engine,
        source: Path,
        window_seconds: float = 10.0,
        error_threshold: float = 5.0,
        volume_multiplier: float = 3.0,
        min_baseline_windows: int = 3,
        quiet: bool = False,
    ) -> None:
        self.engine = engine
        self.quality_engine = quality_engine
        self.source = source
        self.quiet = quiet

        self.window = WindowTracker(window_seconds)
        self.circuit = CircuitBreaker(error_threshold, volume_multiplier, min_baseline_windows)
        self.current_incident_id: Optional[int] = None

        self.total = 0
        self.valid_count = 0
        self.invalid_count = 0
        self.held_by_circuit = 0  # otherwise-valid records held during an open circuit

    # --- per-record handling ---------------------------------------------

    def handle_raw_row(self, raw_row: dict) -> None:
        self.total += 1
        record, parse_error = validate_record(raw_row)

        if parse_error:
            is_valid = False
            streaming_db.store_quarantine(
                self.engine,
                typed_record=EMPTY_TYPED_RECORD,
                raw_record=raw_to_jsonable(raw_row),
                rule="PARSE_ERROR",
                reason=parse_error,
            )
            if not self.quiet:
                print(f"[QUALITY] Failed: {parse_error} (rule=PARSE_ERROR)")
        else:
            result = self.quality_engine.check(record)
            is_valid = result.valid

            if result.valid and self.circuit.is_open:
                # Circuit breaker is open: even a record that individually
                # passes every quality rule is held back, not written to
                # valid_orders, until recovery confirms the pipeline is
                # healthy again.
                streaming_db.store_quarantine(
                    self.engine,
                    typed_record=record,
                    raw_record=record,
                    rule=streaming_db.CIRCUIT_OPEN_RULE,
                    reason=(
                        f"Circuit breaker is {self.circuit.state.value}; holding an "
                        f"otherwise-valid record pending recovery"
                        + (f" (incident #{self.current_incident_id})" if self.current_incident_id else "")
                    ),
                )
                self.held_by_circuit += 1
                if not self.quiet:
                    print(f"[QUALITY] Passed, but circuit is {self.circuit.state.value} -> held")
            elif result.valid:
                streaming_db.store_valid(self.engine, record)
                self.quality_engine.mark_seen(record)
                self.valid_count += 1
                if not self.quiet:
                    print("[QUALITY] Passed")
            else:
                streaming_db.store_quarantine(
                    self.engine,
                    typed_record=record,
                    raw_record=record,
                    rule=result.rule,
                    reason=result.reason,
                )
                if not self.quiet:
                    print(f"[QUALITY] Failed: {result.reason} (rule={result.rule})")

        if not is_valid:
            self.invalid_count += 1

        self.window.add_record(is_valid)
        if self.window.should_close():
            self._close_window()

    # --- window / circuit / incident handling ------------------------------

    def _close_window(self) -> None:
        metrics = self.window.close()
        transition = self.circuit.evaluate_window(metrics)

        print(
            f"[WINDOW] {metrics.total_records} records | "
            f"{metrics.invalid_records} invalid | "
            f"error_rate={metrics.error_rate}% | "
            f"quality_score={metrics.quality_score}% | "
            f"rate={metrics.records_per_sec}/s"
        )
        self._log_transition(transition)

        if transition.opened_incident:
            self.current_incident_id = incidents_db.create_incident(
                self.engine,
                incident_type=transition.anomaly.type,
                severity=transition.anomaly.severity,
                error_rate=transition.anomaly.error_rate,
                description=transition.anomaly.description,
                window_started_at=metrics.started_at_wall,
                window_ended_at=metrics.ended_at_wall,
                records_in_window=metrics.total_records,
                invalid_in_window=metrics.invalid_records,
            )
            print(
                f"[INCIDENT] #{self.current_incident_id} opened | "
                f"type={transition.anomaly.type} severity={transition.anomaly.severity} | "
                f"{transition.anomaly.description}"
            )

        if transition.attempt_recovery:
            self._run_recovery()

    def _run_recovery(self) -> None:
        if self.current_incident_id is not None:
            incidents_db.update_incident_status(self.engine, self.current_incident_id, "RECOVERING")
        print("[RECOVERY] Attempting recovery: re-reading affected records from the source dataset...")

        result = recovery.attempt_recovery(self.engine, self.quality_engine, self.source)
        print(
            f"[RECOVERY] attempted={result.attempted} recovered={result.recovered} "
            f"still_failing={result.still_failing} success={result.success}"
        )

        transition = self.circuit.record_recovery_result(result.success)
        self._log_transition(transition)

        if self.current_incident_id is not None:
            if transition.resolved:
                incidents_db.update_incident_status(self.engine, self.current_incident_id, "RESOLVED", resolved=True)
                print(f"[INCIDENT] #{self.current_incident_id} RESOLVED")
                self.current_incident_id = None
            else:
                incidents_db.update_incident_status(self.engine, self.current_incident_id, "ACTIVE")
                print(f"[INCIDENT] #{self.current_incident_id} still ACTIVE, will retry recovery next window")

    def _log_transition(self, transition: Transition) -> None:
        if transition.changed:
            print(f"[CIRCUIT] {transition.previous_state.value} -> {transition.new_state.value}")

    # --- lifecycle ---------------------------------------------------------

    def finalize(self) -> None:
        """Flush a final partial window so its records aren't left unevaluated."""
        if self.window.pending_count > 0:
            self._close_window()
