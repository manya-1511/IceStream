"""Tests for etl.to_events -- historical records -> streaming-ready JSONL."""

from __future__ import annotations

import json
from pathlib import Path

from etl.preprocess import run as preprocess_run
from etl.schemas import CheckoutEvent
from etl.to_events import run as to_events_run


def test_to_events_writes_one_line_per_record(fixture_raw_dir: Path, tmp_out_dir: Path):
    preprocess_run(fixture_raw_dir, tmp_out_dir)
    output_path = tmp_out_dir / "events" / "checkout_events.jsonl"
    count = to_events_run(tmp_out_dir / "checkout_events.parquet", output_path)

    assert count == 17
    lines = output_path.read_text().strip().splitlines()
    assert len(lines) == 17


def test_to_events_output_is_sorted_by_timestamp(fixture_raw_dir: Path, tmp_out_dir: Path):
    preprocess_run(fixture_raw_dir, tmp_out_dir)
    output_path = tmp_out_dir / "events" / "checkout_events.jsonl"
    to_events_run(tmp_out_dir / "checkout_events.parquet", output_path)

    timestamps = []
    for line in output_path.read_text().strip().splitlines():
        record = json.loads(line)
        timestamps.append(record["timestamp"])
    assert timestamps == sorted(timestamps)


def test_to_events_each_line_is_a_valid_checkout_event(fixture_raw_dir: Path, tmp_out_dir: Path):
    preprocess_run(fixture_raw_dir, tmp_out_dir)
    output_path = tmp_out_dir / "events" / "checkout_events.jsonl"
    to_events_run(tmp_out_dir / "checkout_events.parquet", output_path)

    for line in output_path.read_text().strip().splitlines():
        record = json.loads(line)
        CheckoutEvent.model_validate(record)  # raises if invalid


def test_to_events_transaction_ids_are_unique(fixture_raw_dir: Path, tmp_out_dir: Path):
    preprocess_run(fixture_raw_dir, tmp_out_dir)
    output_path = tmp_out_dir / "events" / "checkout_events.jsonl"
    to_events_run(tmp_out_dir / "checkout_events.parquet", output_path)

    ids = [json.loads(line)["transaction_id"] for line in output_path.read_text().strip().splitlines()]
    assert len(ids) == len(set(ids))
