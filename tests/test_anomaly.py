"""
Day 3 tests: anomaly detectors.

Run with (from the project root):
    pytest tests/test_anomaly.py -v
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitoring"))

from anomaly import detect_error_rate_anomaly, detect_volume_anomaly  # noqa: E402
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


# --- error-rate anomaly ---------------------------------------------------

def test_error_rate_below_threshold_is_not_an_anomaly():
    metrics = make_metrics(total=100, invalid=3)  # 3%
    assert detect_error_rate_anomaly(metrics, threshold=5.0) is None


def test_error_rate_above_threshold_is_an_anomaly():
    metrics = make_metrics(total=100, invalid=18)  # 18%
    anomaly = detect_error_rate_anomaly(metrics, threshold=5.0)
    assert anomaly is not None
    assert anomaly.type == "ERROR_RATE"
    assert anomaly.error_rate == 18.0


def test_error_rate_threshold_is_configurable():
    metrics = make_metrics(total=100, invalid=8)  # 8%
    assert detect_error_rate_anomaly(metrics, threshold=5.0) is not None
    assert detect_error_rate_anomaly(metrics, threshold=10.0) is None


def test_error_rate_severity_scales_with_how_far_over_threshold():
    low = detect_error_rate_anomaly(make_metrics(100, 6), threshold=5.0)     # 6%, just over
    medium = detect_error_rate_anomaly(make_metrics(100, 12), threshold=5.0)  # 12%, 2.4x
    high = detect_error_rate_anomaly(make_metrics(100, 30), threshold=5.0)   # 30%, 6x
    assert low.severity == "LOW"
    assert medium.severity == "MEDIUM"
    assert high.severity == "HIGH"


def test_empty_window_has_no_error_rate_anomaly():
    metrics = make_metrics(total=0, invalid=0)
    assert detect_error_rate_anomaly(metrics, threshold=5.0) is None


# --- volume anomaly --------------------------------------------------------

def test_volume_anomaly_needs_a_baseline_first():
    metrics = make_metrics(total=100, invalid=0, records_per_sec=100.0)
    # only 2 prior windows recorded -> not enough history yet
    result = detect_volume_anomaly(metrics, rate_history=[10.0, 11.0], multiplier=3.0, min_baseline_windows=3)
    assert result is None


def test_volume_within_normal_range_is_not_an_anomaly():
    metrics = make_metrics(total=100, invalid=0, records_per_sec=12.0)
    result = detect_volume_anomaly(metrics, rate_history=[10.0, 10.0, 10.0], multiplier=3.0)
    assert result is None


def test_volume_spike_is_an_anomaly():
    metrics = make_metrics(total=100, invalid=0, records_per_sec=50.0)  # 5x baseline of 10
    result = detect_volume_anomaly(metrics, rate_history=[10.0, 10.0, 10.0], multiplier=3.0)
    assert result is not None
    assert result.type == "VOLUME"
    assert result.severity == "HIGH"
