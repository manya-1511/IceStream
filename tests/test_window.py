"""
Day 3 tests: window-based monitoring metrics.

Run with (from the project root):
    pytest tests/test_window.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitoring"))

from window import WindowTracker  # noqa: E402


def test_window_closes_after_duration():
    tracker = WindowTracker(window_seconds=10.0)
    assert tracker.should_close(now=tracker._start + 5) is False
    assert tracker.should_close(now=tracker._start + 10) is True
    assert tracker.should_close(now=tracker._start + 11) is True


def test_metrics_computed_correctly():
    tracker = WindowTracker(window_seconds=10.0)
    start = tracker._start

    for _ in range(8):
        tracker.add_record(is_valid=True)
    for _ in range(2):
        tracker.add_record(is_valid=False)

    metrics = tracker.close(now=start + 10.0)

    assert metrics.total_records == 10
    assert metrics.valid_records == 8
    assert metrics.invalid_records == 2
    assert metrics.error_rate == 20.0
    assert metrics.quality_score == 80.0
    assert metrics.records_per_sec == 1.0


def test_empty_window_is_100pct_healthy():
    tracker = WindowTracker(window_seconds=10.0)
    metrics = tracker.close(now=tracker._start + 10.0)

    assert metrics.total_records == 0
    assert metrics.error_rate == 0.0
    assert metrics.quality_score == 100.0


def test_close_starts_a_fresh_window():
    tracker = WindowTracker(window_seconds=10.0)
    tracker.add_record(is_valid=True)
    tracker.close(now=tracker._start + 10.0)

    assert tracker.pending_count == 0
