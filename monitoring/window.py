"""
Window-based monitoring.

WindowTracker accumulates records as they stream through, and closes a
"window" every `window_seconds` (default 10, per the spec), producing a
WindowMetrics snapshot: total records, invalid records, error rate,
quality score, and records/sec — the numbers the anomaly detectors
(monitoring/anomaly.py) and circuit breaker (monitoring/circuit_breaker.py)
act on.

This is deliberately just counting + arithmetic — no threading, no timers,
no background jobs. The streaming loop calls `should_close(now)` after
each record and closes the window when enough time has passed. That's the
whole mechanism, which is what keeps this understandable and testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WindowMetrics:
    started_at: float          # time.monotonic() when the window opened
    ended_at: float            # time.monotonic() when the window closed
    started_at_wall: datetime  # wall-clock equivalents, for logging/incidents
    ended_at_wall: datetime
    total_records: int
    invalid_records: int
    valid_records: int
    error_rate: float          # percentage, 0-100
    quality_score: float       # percentage, 0-100
    records_per_sec: float

    @property
    def duration_seconds(self) -> float:
        return max(self.ended_at - self.started_at, 0.0001)  # avoid div-by-zero


class WindowTracker:
    def __init__(self, window_seconds: float = 10.0) -> None:
        self.window_seconds = window_seconds
        self._start = time.monotonic()
        self._start_wall = datetime.now()
        self._total = 0
        self._invalid = 0

    @property
    def pending_count(self) -> int:
        """Records accumulated in the current, not-yet-closed window."""
        return self._total

    def add_record(self, is_valid: bool) -> None:
        self._total += 1
        if not is_valid:
            self._invalid += 1

    def should_close(self, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        # A tiny epsilon avoids floating-point rounding (e.g. start + 10.0
        # sometimes evaluating to 9.999999999998 due to float addition)
        # making an exact window boundary look like it hasn't closed yet.
        return (now - self._start) >= (self.window_seconds - 1e-9)

    def close(self, now: float | None = None) -> WindowMetrics:
        """
        Closes the current window, returns its metrics, and immediately
        starts a fresh window (so the caller doesn't need a separate
        reset() call).
        """
        now = now if now is not None else time.monotonic()
        started_at = self._start
        started_at_wall = self._start_wall
        ended_at_wall = datetime.now()
        total = self._total
        invalid = self._invalid
        valid = total - invalid
        duration = max(now - started_at, 0.0001)

        metrics = WindowMetrics(
            started_at=started_at,
            ended_at=now,
            started_at_wall=started_at_wall,
            ended_at_wall=ended_at_wall,
            total_records=total,
            invalid_records=invalid,
            valid_records=valid,
            error_rate=round((invalid / total) * 100, 2) if total else 0.0,
            quality_score=round((valid / total) * 100, 2) if total else 100.0,
            records_per_sec=round(total / duration, 2),
        )

        # start the next window
        self._start = now
        self._start_wall = ended_at_wall
        self._total = 0
        self._invalid = 0

        return metrics
