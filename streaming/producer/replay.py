"""
streaming/producer/replay.py -- core logic for publishing IceStream
checkout events to Kafka.

Two send modes:
  - "fixed-rate": send at a constant configured events/second.
  - "replay":     send preserving the *relative* time gaps between the
                  original events' timestamps (scaled by --replay-speed),
                  so a burst of orders in the source data produces a
                  burst on the topic too, just compressed in time.

Does NOT implement anomaly injection -- every event is either published
as-is (schema-validated) or routed to the DLQ topic if it fails
validation. No field is corrupted or synthesized here.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from etl.schemas import CheckoutEvent

logger = logging.getLogger("streaming.producer")


class EventSender(Protocol):
    """Anything that can send a keyed message to a topic. Implemented by
    both the real Kafka-backed sender and the in-memory dry-run sender
    used in tests -- see KafkaEventSender / DryRunEventSender below."""

    def send(self, topic: str, key: str | None, value: str) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


class KafkaEventSender:
    """Wraps kafka-python's KafkaProducer. Imported lazily so dry-run mode
    (and tests) never require kafka-python to be installed/importable."""

    def __init__(self, bootstrap_servers: str) -> None:
        from kafka import KafkaProducer  # noqa: PLC0415 - intentional lazy import
        from kafka.errors import KafkaError  # noqa: PLC0415

        self._KafkaError = KafkaError
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
            value_serializer=lambda v: v.encode("utf-8"),
            acks="all",
            retries=5,
            linger_ms=10,
        )

    def send(self, topic: str, key: str | None, value: str) -> None:
        future = self._producer.send(topic, key=key, value=value)
        future.add_errback(self._on_error, topic=topic)

    def _on_error(self, exc: Exception, topic: str) -> None:
        logger.error("Failed to deliver message to topic %s: %s", topic, exc)

    def flush(self) -> None:
        self._producer.flush()

    def close(self) -> None:
        self._producer.close()


@dataclass
class DryRunEventSender:
    """In-memory sender for --dry-run and for tests -- never touches a
    real broker. Records every (topic, key, value) tuple it would have
    sent."""

    sent: list[tuple[str, str | None, str]] = field(default_factory=list)

    def send(self, topic: str, key: str | None, value: str) -> None:
        self.sent.append((topic, key, value))

    def flush(self) -> None:  # no-op
        pass

    def close(self) -> None:  # no-op
        pass


def load_events(input_path: Path, max_records: int | None = None) -> list[dict[str, Any]]:
    """Load raw JSON records from a JSON Lines file, in file order (the
    etl.to_events output is already sorted by timestamp). Returns raw
    dicts -- schema validation happens per-record in run() so a single
    bad line can be routed to the DLQ instead of aborting the whole
    load."""
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. Run `python -m etl.preprocess` "
            f"and `python -m etl.to_events` first."
        )

    records: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping unparseable line %d in %s: %s", line_no, input_path, exc)
            if max_records is not None and len(records) >= max_records:
                break
    return records


def _fixed_rate_delays(count: int, events_per_second: float) -> Iterator[float]:
    """Yields the sleep duration to wait *before* sending the i-th event."""
    interval = 1.0 / events_per_second if events_per_second > 0 else 0.0
    for i in range(count):
        yield 0.0 if i == 0 else interval


def _replay_delays(records: list[dict[str, Any]], speed: float) -> Iterator[float]:
    """Yields the sleep duration to wait before sending the i-th event,
    derived from the real gap between consecutive source timestamps,
    compressed by `speed` (speed=60 means 60x faster than real time)."""
    if not records:
        return
    prev_ts: datetime | None = None
    for record in records:
        ts_raw = record.get("timestamp")
        try:
            ts = datetime.fromisoformat(ts_raw) if ts_raw else None
        except (TypeError, ValueError):
            ts = None

        if prev_ts is None or ts is None:
            yield 0.0
        else:
            gap_seconds = max(0.0, (ts - prev_ts).total_seconds())
            yield gap_seconds / speed if speed > 0 else 0.0

        if ts is not None:
            prev_ts = ts


@dataclass
class RunStats:
    sent: int = 0
    dlq: int = 0
    parse_errors: int = 0

    @property
    def total(self) -> int:
        return self.sent + self.dlq + self.parse_errors


def run(
    *,
    input_path: Path,
    sender: EventSender,
    topic: str,
    dlq_topic: str,
    mode: Literal["fixed-rate", "replay"] = "fixed-rate",
    events_per_second: float = 10.0,
    replay_speed: float = 60.0,
    max_records: int | None = None,
    loop: bool = False,
    log_interval_seconds: float = 5.0,
    sleep_fn=time.sleep,
    now_fn=time.monotonic,
) -> RunStats:
    """Publish events to Kafka. Returns final RunStats. `sleep_fn`/`now_fn`
    are injectable so tests can run this without real wall-clock delays."""
    records = load_events(input_path, max_records=max_records)
    if not records:
        logger.warning("No records loaded from %s -- nothing to publish.", input_path)
        return RunStats()

    logger.info(
        "Loaded %d record(s) from %s | mode=%s | topic=%s | dlq_topic=%s",
        len(records),
        input_path,
        mode,
        topic,
        dlq_topic,
    )

    stats = RunStats()
    run_start = now_fn()
    last_log_time = run_start
    last_log_sent = 0

    keep_going = True
    while keep_going:
        delays = (
            _fixed_rate_delays(len(records), events_per_second)
            if mode == "fixed-rate"
            else _replay_delays(records, replay_speed)
        )

        for record, delay in zip(records, delays):
            if delay > 0:
                sleep_fn(delay)

            _publish_one(record, sender=sender, topic=topic, dlq_topic=dlq_topic, stats=stats)

            now = now_fn()
            if now - last_log_time >= log_interval_seconds:
                elapsed = now - last_log_time
                rate = (stats.sent - last_log_sent) / elapsed if elapsed > 0 else 0.0
                logger.info(
                    "Throughput: %.2f events/sec | sent=%d dlq=%d parse_errors=%d",
                    rate,
                    stats.sent,
                    stats.dlq,
                    stats.parse_errors,
                )
                last_log_time = now
                last_log_sent = stats.sent

        keep_going = loop

    sender.flush()
    total_elapsed = now_fn() - run_start
    avg_rate = stats.sent / total_elapsed if total_elapsed > 0 else 0.0
    logger.info(
        "Run complete: sent=%d dlq=%d parse_errors=%d | elapsed=%.2fs | avg=%.2f events/sec",
        stats.sent,
        stats.dlq,
        stats.parse_errors,
        total_elapsed,
        avg_rate,
    )
    return stats


def _publish_one(
    record: dict[str, Any],
    *,
    sender: EventSender,
    topic: str,
    dlq_topic: str,
    stats: RunStats,
) -> None:
    try:
        event = CheckoutEvent.model_validate(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Record failed schema validation, routing to DLQ (order_id=%s): %s",
            record.get("order_id"),
            exc,
        )
        dlq_envelope = json.dumps({"error": str(exc), "raw_record": record}, default=str)
        sender.send(dlq_topic, record.get("order_id"), dlq_envelope)
        stats.dlq += 1
        return

    sender.send(topic, event.order_id, event.model_dump_json())
    stats.sent += 1
