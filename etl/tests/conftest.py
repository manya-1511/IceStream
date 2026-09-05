from __future__ import annotations

from pathlib import Path

import pytest

from etl.constants import FIXTURE_RAW_DIR


@pytest.fixture
def fixture_raw_dir() -> Path:
    return FIXTURE_RAW_DIR


@pytest.fixture
def tmp_out_dir(tmp_path: Path) -> Path:
    return tmp_path / "processed"
