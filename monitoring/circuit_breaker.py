"""
The circuit breaker state machine:

    HEALTHY -> DEGRADED -> QUARANTINED -> RECOVERING -> HEALTHY

This class holds NO database connection and does NO I/O — it only tracks
state and decides what *should* happen next, given a window's metrics. The
orchestrator (monitoring/pipeline.py) is responsible for acting on that
decision (creating/updating incident rows, running recovery). This split
is what makes the state machine itself trivially unit-testable — see
tests/test_circuit_breaker.py — and easy to reason about in isolation.

State meanings:
    HEALTHY      normal operation. Records are stored exactly as the
                 quality engine decides (valid -> valid_orders,
                 invalid -> quarantine_orders).
    DEGRADED     some invalid records this window, but not enough to
                 cross the anomaly threshold. Same storage behavior as
                 HEALTHY — this is a "watch" state, not an incident.
    QUARANTINED  an anomaly was detected. The circuit is "open": every
                 record, valid or not, is held in quarantine_orders until
                 the pipeline recovers (see monitoring/pipeline.py for how
                 storage routing changes).
    RECOVERING   one full window has now passed while QUARANTINED, so an
                 automatic recovery attempt runs (monitoring/recovery.py).
                 If it succeeds, state returns to HEALTHY. If not, state
                 goes back to QUARANTINED to try again next window.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from anomaly import Anomaly, detect_error_rate_anomaly, detect_volume_anomaly
from window import WindowMetrics


class CircuitState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"
    RECOVERING = "RECOVERING"


@dataclass
class Transition:
    previous_state: CircuitState
    new_state: CircuitState
    anomaly: Optional[Anomaly] = None   # set only when a NEW incident should be opened
    opened_incident: bool = False       # True -> caller should INSERT a new incidents row
    attempt_recovery: bool = False      # True -> caller should run the recovery procedure now
    resolved: bool = False              # True -> caller should mark the incident RESOLVED

    @property
    def changed(self) -> bool:
        return self.previous_state != self.new_state


class CircuitBreaker:
    def __init__(
        self,
        error_threshold: float = 5.0,
        volume_multiplier: float = 3.0,
        min_baseline_windows: int = 3,
        history_size: int = 10,
    ) -> None:
        self.state = CircuitState.HEALTHY
        self.error_threshold = error_threshold
        self.volume_multiplier = volume_multiplier
        self.min_baseline_windows = min_baseline_windows
        self.history_size = history_size

        self._rate_history: list[float] = []  # records/sec of past CLOSED windows only

    def evaluate_window(self, metrics: WindowMetrics) -> Transition:
        """
        Call once per closed window. Decides the next state:
          - HEALTHY/DEGRADED -> check for a new anomaly; if found, open
            the circuit (QUARANTINED) and signal an incident should be
            created. Otherwise settle into HEALTHY or DEGRADED depending
            on whether this window had any invalid records.
          - QUARANTINED -> a full window has now passed with the circuit
            open, so move to RECOVERING and signal a recovery attempt.
          - RECOVERING -> not touched here; see record_recovery_result().
        """
        previous = self.state
        transition = Transition(previous_state=previous, new_state=previous)

        if self.state in (CircuitState.HEALTHY, CircuitState.DEGRADED):
            anomaly = detect_error_rate_anomaly(
                metrics, self.error_threshold
            ) or detect_volume_anomaly(
                metrics, self._rate_history, self.volume_multiplier, self.min_baseline_windows
            )

            if anomaly:
                self.state = CircuitState.QUARANTINED
                transition = Transition(
                    previous_state=previous,
                    new_state=self.state,
                    anomaly=anomaly,
                    opened_incident=True,
                )
            elif metrics.invalid_records > 0:
                self.state = CircuitState.DEGRADED
                transition = Transition(previous, self.state)
            else:
                self.state = CircuitState.HEALTHY
                transition = Transition(previous, self.state)

        elif self.state == CircuitState.QUARANTINED:
            self.state = CircuitState.RECOVERING
            transition = Transition(previous, self.state, attempt_recovery=True)

        # RECOVERING: no window-driven transition; handled by record_recovery_result()

        # Volume baseline only reflects *normal* history — don't let an
        # already-anomalous window pollute the baseline used to detect
        # the next one.
        if not transition.opened_incident:
            self._rate_history.append(metrics.records_per_sec)
            if len(self._rate_history) > self.history_size:
                self._rate_history.pop(0)

        return transition

    def record_recovery_result(self, success: bool) -> Transition:
        """
        Call after a recovery attempt (monitoring/recovery.py) completes.
        success=True  -> RECOVERING -> HEALTHY, incident should be resolved
        success=False -> RECOVERING -> QUARANTINED, incident stays open,
                          will attempt recovery again after the next window
        """
        previous = self.state
        if success:
            self.state = CircuitState.HEALTHY
            return Transition(previous, self.state, resolved=True)
        else:
            self.state = CircuitState.QUARANTINED
            return Transition(previous, self.state)

    @property
    def is_open(self) -> bool:
        """True when the circuit is not accepting records into normal storage."""
        return self.state in (CircuitState.QUARANTINED, CircuitState.RECOVERING)
