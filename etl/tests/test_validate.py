"""Tests for etl.validate — run against output produced by etl.preprocess
on the fixture dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl.preprocess import run as preprocess_run
from etl.validate import (
    check_price_sanity,
    check_referential_completeness,
    check_timestamp_range,
    check_uniqueness,
    validate_schema,
)
from etl.validate import run as validate_run


def _processed_df(fixture_raw_dir: Path, tmp_out_dir: Path) -> pd.DataFrame:
    return preprocess_run(fixture_raw_dir, tmp_out_dir)


def test_fixture_output_passes_schema_validation(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = _processed_df(fixture_raw_dir, tmp_out_dir)
    valid, total, errors = validate_schema(df)
    assert valid == total
    assert errors == []


def test_fixture_output_has_no_duplicate_transaction_ids(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = _processed_df(fixture_raw_dir, tmp_out_dir)
    assert check_uniqueness(df) == []


def test_fixture_output_has_no_null_required_ids(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = _processed_df(fixture_raw_dir, tmp_out_dir)
    nulls = check_referential_completeness(df)
    assert all(v == 0 for v in nulls.values())


def test_fixture_output_within_known_timestamp_range(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = _processed_df(fixture_raw_dir, tmp_out_dir)
    assert len(check_timestamp_range(df)) == 0


def test_fixture_output_prices_are_sane(fixture_raw_dir: Path, tmp_out_dir: Path):
    df = _processed_df(fixture_raw_dir, tmp_out_dir)
    assert len(check_price_sanity(df)) == 0


def test_duplicate_transaction_id_is_detected():
    df = pd.DataFrame(
        [
            {"transaction_id": "dup-1", "order_id": "a", "customer_id": "c1"},
            {"transaction_id": "dup-1", "order_id": "b", "customer_id": "c2"},
        ]
    )
    dupes = check_uniqueness(df)
    assert dupes == ["dup-1"]


def test_end_to_end_validate_run_passes_on_fixture_output(fixture_raw_dir: Path, tmp_out_dir: Path):
    preprocess_run(fixture_raw_dir, tmp_out_dir)
    ok = validate_run(tmp_out_dir / "checkout_events.parquet", max_error_rate=0.01)
    assert ok is True
