"""
Anomaly detection.

Two detectors, both simple threshold checks on a WindowMetrics snapshot —
no machine learning, because a moving average and a percentage threshold
are genuinely enough to catch the two anomaly types the spec asks for, and
are easy to explain and reason about.

Both detectors return an Anomaly (or None if nothing's wrong). The circuit
breaker (monitoring/circuit_breaker.py) decides what to *do* about an
anomaly; these functions only decide whether one exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from window import WindowMetrics


@dataclass
class Anomaly:
    type: str           # 'ERROR_RATE' or 'VOLUME'
    severity: str        # 'LOW', 'MEDIUM', 'HIGH'
    error_rate: Optional[float]
    description: str


def _error_rate_severity(error_rate: float, threshold: float) -> str:
    """The further past the threshold, the more severe."""
    if error_rate >= threshold * 4:
        return "HIGH"
    if error_rate >= threshold * 2:
        return "MEDIUM"
    return "LOW"


def detect_error_rate_anomaly(metrics: WindowMetrics, threshold: float = 5.0) -> Optional[Anomaly]:
    """
    The spec's rule: error_rate > threshold (default 5%) triggers an
    incident. `threshold` is a parameter specifically so it's configurable
    (see run_monitored_stream.py --error-threshold), not hardcoded.
    """
    if metrics.total_records == 0:
        return None
    if metrics.error_rate <= threshold:
        return None

    return Anomaly(
        type="ERROR_RATE",
        severity=_error_rate_severity(metrics.error_rate, threshold),
        error_rate=metrics.error_rate,
        description=(
            f"error_rate {metrics.error_rate}% exceeded threshold {threshold}% "
            f"({metrics.invalid_records}/{metrics.total_records} records invalid "
            f"in a {metrics.duration_seconds:.1f}s window)"
        ),
    )


def _volume_severity(ratio: float) -> str:
    if ratio >= 5:
        return "HIGH"
    if ratio >= 4:
        return "MEDIUM"
    return "LOW"


def detect_volume_anomaly(
    metrics: WindowMetrics,
    rate_history: list[float],
    multiplier: float = 3.0,
    min_baseline_windows: int = 3,
) -> Optional[Anomaly]:
    """
    Compares this window's records/sec against the average of the last
    `min_baseline_windows` (or more) prior windows. If the current rate is
    more than `multiplier`x that baseline, it's flagged as a volume
    anomaly — an unusual, sudden increase in traffic compared to recent
    normal activity.

    `rate_history` should NOT include the current window (only prior,
    already-closed windows) — the caller (circuit breaker) is responsible
    for that ordering.

    Returns None if there isn't enough history yet to establish a
    baseline (avoids false positives on startup, when there's nothing to
    compare against).
    """
    if len(rate_history) < min_baseline_windows:
        return None

    baseline = sum(rate_history) / len(rate_history)
    if baseline <= 0:
        return None  # no meaningful baseline to compare against

    ratio = metrics.records_per_sec / baseline
    if ratio <= multiplier:
        return None

    return Anomaly(
        type="VOLUME",
        severity=_volume_severity(ratio),
        error_rate=metrics.error_rate if metrics.invalid_records else None,
        description=(
            f"records/sec {metrics.records_per_sec} is {ratio:.1f}x the recent "
            f"baseline of {baseline:.2f} (threshold: {multiplier}x)"
        ),
    )
