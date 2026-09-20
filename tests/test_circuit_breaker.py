"""
Day 3 tests: every circuit breaker state transition.

    HEALTHY -> DEGRADED -> QUARANTINED -> RECOVERING -> HEALTHY
                  ^                                        |
                  +----------------------------------------+
                  (also: QUARANTINED -> RECOVERING -> QUARANTINED
                   when a recovery attempt fails)

CircuitBreaker has no database dependency (see monitoring/circuit_breaker.py),
so these tests run purely in memory — no Postgres needed.

Run with (from the project root):
    pytest tests/test_circuit_breaker.py -v
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitoring"))

from circuit_breaker import CircuitBreaker, CircuitState  # noqa: E402
from window import WindowMetrics  # noqa: E402


def make_metrics(total, invalid, records_per_sec=10.0) -> WindowMetrics:
    valid = total - invalid
    now = datetime.now()
    return WindowMetrics(
        started_at=0.0,
        ended_at=10.0,
        started_at_wall=now,
        ended_at_wall=now,
        total_records=total,
        invalid_records=invalid,
        valid_records=valid,
        error_rate=round((invalid / total) * 100, 2) if total else 0.0,
        quality_score=round((valid / total) * 100, 2) if total else 100.0,
        records_per_sec=records_per_sec,
    )


def test_starts_healthy():
    breaker = CircuitBreaker()
    assert breaker.state == CircuitState.HEALTHY
    assert breaker.is_open is False


def test_healthy_stays_healthy_with_no_errors():
    breaker = CircuitBreaker(error_threshold=5.0)
    transition = breaker.evaluate_window(make_metrics(total=100, invalid=0))
    assert transition.previous_state == CircuitState.HEALTHY
    assert transition.new_state == CircuitState.HEALTHY
    assert transition.changed is False


def test_healthy_to_degraded_on_some_errors_below_threshold():
    breaker = CircuitBreaker(error_threshold=5.0)
    transition = breaker.evaluate_window(make_metrics(total=100, invalid=2))  # 2%, below 5%
    assert transition.previous_state == CircuitState.HEALTHY
    assert transition.new_state == CircuitState.DEGRADED
    assert transition.changed is True
    assert transition.opened_incident is False


def test_degraded_back_to_healthy_when_errors_stop():
    breaker = CircuitBreaker(error_threshold=5.0)
    breaker.evaluate_window(make_metrics(total=100, invalid=2))  # -> DEGRADED
    assert breaker.state == CircuitState.DEGRADED

    transition = breaker.evaluate_window(make_metrics(total=100, invalid=0))  # clean window
    assert transition.previous_state == CircuitState.DEGRADED
    assert transition.new_state == CircuitState.HEALTHY


def test_healthy_to_quarantined_on_error_rate_anomaly():
    breaker = CircuitBreaker(error_threshold=5.0)
    transition = breaker.evaluate_window(make_metrics(total=100, invalid=20))  # 20%, well over 5%
    assert transition.previous_state == CircuitState.HEALTHY
    assert transition.new_state == CircuitState.QUARANTINED
    assert transition.opened_incident is True
    assert transition.anomaly is not None
    assert transition.anomaly.type == "ERROR_RATE"
    assert breaker.is_open is True


def test_degraded_to_quarantined_on_error_rate_anomaly():
    breaker = CircuitBreaker(error_threshold=5.0)
    breaker.evaluate_window(make_metrics(total=100, invalid=2))  # -> DEGRADED
    transition = breaker.evaluate_window(make_metrics(total=100, invalid=20))  # -> QUARANTINED
    assert transition.previous_state == CircuitState.DEGRADED
    assert transition.new_state == CircuitState.QUARANTINED
    assert transition.opened_incident is True


def test_quarantined_moves_to_recovering_after_one_full_window():
    breaker = CircuitBreaker(error_threshold=5.0)
    breaker.evaluate_window(make_metrics(total=100, invalid=20))  # -> QUARANTINED
    assert breaker.state == CircuitState.QUARANTINED

    # A full window has now passed while the circuit was open.
    transition = breaker.evaluate_window(make_metrics(total=50, invalid=0))
    assert transition.previous_state == CircuitState.QUARANTINED
    assert transition.new_state == CircuitState.RECOVERING
    assert transition.attempt_recovery is True
    assert breaker.is_open is True  # still not accepting normal writes


def test_recovering_to_healthy_on_successful_recovery():
    breaker = CircuitBreaker(error_threshold=5.0)
    breaker.evaluate_window(make_metrics(total=100, invalid=20))   # -> QUARANTINED
    breaker.evaluate_window(make_metrics(total=50, invalid=0))     # -> RECOVERING
    assert breaker.state == CircuitState.RECOVERING

    transition = breaker.record_recovery_result(success=True)
    assert transition.previous_state == CircuitState.RECOVERING
    assert transition.new_state == CircuitState.HEALTHY
    assert transition.resolved is True
    assert breaker.is_open is False


def test_recovering_back_to_quarantined_on_failed_recovery():
    breaker = CircuitBreaker(error_threshold=5.0)
    breaker.evaluate_window(make_metrics(total=100, invalid=20))   # -> QUARANTINED
    breaker.evaluate_window(make_metrics(total=50, invalid=0))     # -> RECOVERING
    assert breaker.state == CircuitState.RECOVERING

    transition = breaker.record_recovery_result(success=False)
    assert transition.previous_state == CircuitState.RECOVERING
    assert transition.new_state == CircuitState.QUARANTINED
    assert transition.resolved is False
    assert breaker.is_open is True


def test_full_cycle_healthy_to_healthy():
    """The complete loop described in the spec, start to finish."""
    breaker = CircuitBreaker(error_threshold=5.0)
    assert breaker.state == CircuitState.HEALTHY

    t1 = breaker.evaluate_window(make_metrics(100, 1))    # HEALTHY -> DEGRADED
    assert t1.new_state == CircuitState.DEGRADED

    t2 = breaker.evaluate_window(make_metrics(100, 25))   # DEGRADED -> QUARANTINED
    assert t2.new_state == CircuitState.QUARANTINED
    assert t2.opened_incident is True

    t3 = breaker.evaluate_window(make_metrics(50, 0))     # QUARANTINED -> RECOVERING
    assert t3.new_state == CircuitState.RECOVERING
    assert t3.attempt_recovery is True

    t4 = breaker.record_recovery_result(success=True)     # RECOVERING -> HEALTHY
    assert t4.new_state == CircuitState.HEALTHY
    assert t4.resolved is True

    assert breaker.state == CircuitState.HEALTHY
    assert breaker.is_open is False


def test_volume_anomaly_also_opens_the_circuit():
    breaker = CircuitBreaker(error_threshold=5.0, volume_multiplier=3.0, min_baseline_windows=2)
    # Establish a quiet baseline first (no anomaly, no errors).
    breaker.evaluate_window(make_metrics(total=100, invalid=0, records_per_sec=10.0))
    breaker.evaluate_window(make_metrics(total=100, invalid=0, records_per_sec=10.0))
    assert breaker.state == CircuitState.HEALTHY

    # Sudden volume spike, no quality errors at all.
    transition = breaker.evaluate_window(make_metrics(total=500, invalid=0, records_per_sec=50.0))
    assert transition.new_state == CircuitState.QUARANTINED
    assert transition.anomaly.type == "VOLUME"
