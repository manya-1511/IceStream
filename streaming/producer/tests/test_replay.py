"""Tests for streaming.producer.replay -- run entirely with the
DryRunEventSender, so no Kafka broker is needed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etl.schemas import CheckoutEvent
from streaming.producer.replay import (
    DryRunEventSender,
    RunStats,
    _fixed_rate_delays,
    _replay_delays,
    load_events,
    run,
)


def test_load_events_reads_all_sample_records(sample_jsonl: Path):
    records = load_events(sample_jsonl)
    assert len(records) == 17


def test_load_events_respects_max_records(sample_jsonl: Path):
    records = load_events(sample_jsonl, max_records=5)
    assert len(records) == 5


def test_load_events_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_events(tmp_path / "does_not_exist.jsonl")


def test_fixed_rate_delays_first_is_zero_rest_is_interval():
    delays = list(_fixed_rate_delays(3, events_per_second=2.0))
    assert delays[0] == 0.0
    assert delays[1] == pytest.approx(0.5)
    assert delays[2] == pytest.approx(0.5)


def test_replay_delays_first_is_zero_and_matches_gap():
    records = [
        {"timestamp": "2017-01-01T00:00:00"},
        {"timestamp": "2017-01-01T00:01:00"},  # 60s gap
    ]
    delays = list(_replay_delays(records, speed=60.0))
    assert delays[0] == 0.0
    assert delays[1] == pytest.approx(1.0)  # 60s / 60x speed = 1s


def test_replay_delays_handles_missing_timestamp_gracefully():
    records = [{"timestamp": "2017-01-01T00:00:00"}, {}, {"timestamp": "2017-01-01T00:01:00"}]
    delays = list(_replay_delays(records, speed=60.0))
    assert len(delays) == 3
    assert delays[1] == 0.0  # no timestamp on this record -> no delay computed


def test_run_dry_run_sends_all_valid_records(sample_jsonl: Path):
    sender = DryRunEventSender()
    stats = run(
        input_path=sample_jsonl,
        sender=sender,
        topic="checkout-events",
        dlq_topic="checkout-events.dlq",
        events_per_second=1000.0,
        sleep_fn=lambda _: None,  # no real sleeping in tests
    )
    assert stats.sent == 17
    assert stats.dlq == 0
    assert len(sender.sent) == 17
    assert all(topic == "checkout-events" for topic, _, _ in sender.sent)


def test_run_routes_invalid_record_to_dlq(jsonl_with_bad_record: Path):
    sender = DryRunEventSender()
    stats = run(
        input_path=jsonl_with_bad_record,
        sender=sender,
        topic="checkout-events",
        dlq_topic="checkout-events.dlq",
        events_per_second=1000.0,
        sleep_fn=lambda _: None,
    )
    assert stats.dlq == 1
    assert stats.sent == 17  # 17 valid sample records + 1 bad record inserted
    dlq_messages = [v for topic, _, v in sender.sent if topic == "checkout-events.dlq"]
    assert len(dlq_messages) == 1
    envelope = json.loads(dlq_messages[0])
    assert envelope["raw_record"]["order_id"] == "ord_broken"
    assert "error" in envelope


def test_run_respects_max_records(sample_jsonl: Path):
    sender = DryRunEventSender()
    stats = run(
        input_path=sample_jsonl,
        sender=sender,
        topic="checkout-events",
        dlq_topic="checkout-events.dlq",
        max_records=5,
        events_per_second=1000.0,
        sleep_fn=lambda _: None,
    )
    assert stats.sent == 5


def test_run_published_values_are_valid_checkout_events(sample_jsonl: Path):
    """The exact thing published to Kafka must round-trip through the
    canonical schema -- this is the "JSON matches our event schema" check."""
    sender = DryRunEventSender()
    run(
        input_path=sample_jsonl,
        sender=sender,
        topic="checkout-events",
        dlq_topic="checkout-events.dlq",
        events_per_second=1000.0,
        sleep_fn=lambda _: None,
    )
    for topic, key, value in sender.sent:
        assert topic == "checkout-events"
        parsed = json.loads(value)
        event = CheckoutEvent.model_validate(parsed)
        assert key == event.order_id  # partitioning key is order_id


def test_run_key_is_order_id_for_partitioning(sample_jsonl: Path):
    sender = DryRunEventSender()
    run(
        input_path=sample_jsonl,
        sender=sender,
        topic="checkout-events",
        dlq_topic="checkout-events.dlq",
        events_per_second=1000.0,
        sleep_fn=lambda _: None,
    )
    keys = {key for _, key, _ in sender.sent}
    assert None not in keys
    assert all(isinstance(k, str) and k.startswith("ord_") for k in keys)


def test_run_stats_total_property():
    stats = RunStats(sent=5, dlq=2, parse_errors=1)
    assert stats.total == 8


def test_run_loop_sends_multiple_passes(sample_jsonl: Path):
    """--loop should keep sending; we cap iterations by stopping after two
    passes worth of records via a sleep_fn that raises after enough calls,
    simulating the operator hitting Ctrl+C."""
    sender = DryRunEventSender()
    call_count = {"n": 0}

    def counting_sleep(_delay: float) -> None:
        call_count["n"] += 1
        if call_count["n"] > 20:  # more than one pass (17 records) but not too many
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run(
            input_path=sample_jsonl,
            sender=sender,
            topic="checkout-events",
            dlq_topic="checkout-events.dlq",
            events_per_second=1000.0,
            loop=True,
            sleep_fn=counting_sleep,
        )
    # First pass (17 records) should have completed before the second pass
    # was interrupted.
    assert sender.sent  # something was sent across the (partial) second pass too
    assert len([1 for t, _, _ in sender.sent if t == "checkout-events"]) >= 17
