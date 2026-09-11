from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_JSONL = REPO_ROOT / "data" / "samples" / "checkout_events_sample.jsonl"


@pytest.fixture
def sample_jsonl() -> Path:
    return SAMPLE_JSONL


@pytest.fixture
def jsonl_with_bad_record(tmp_path: Path, sample_jsonl: Path) -> Path:
    """A copy of the sample data with one intentionally invalid record
    inserted, to exercise the DLQ path in tests."""
    lines = sample_jsonl.read_text().splitlines()
    bad_line = '{"order_id": "ord_broken", "customer_id": "cust_broken", "not_a_valid_event": true}'
    mixed = lines[:2] + [bad_line] + lines[2:]
    out_path = tmp_path / "with_bad_record.jsonl"
    out_path.write_text("\n".join(mixed) + "\n")
    return out_path
