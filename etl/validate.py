"""
etl/validate.py — validate processed checkout events and print a report.

Usage:
    python -m etl.validate                                   # validates data/processed/checkout_events.parquet
    python -m etl.validate --input data/processed/checkout_events.parquet

Checks performed (each one real, against the actual data — no check here
ever reports success without having run):
    1. Schema validation — every row against etl.schemas.CheckoutEvent.
    2. Uniqueness — transaction_id must be unique.
    3. Referential completeness — order_id / customer_id / product_id non-null.
    4. Timestamp sanity — within the known Olist collection window (2016-09-01
       to 2018-12-31); flags anything outside that as a warning, not a hard
       failure (a real download could legitimately extend this range).
    5. Price sanity — unit_price and total_amount within a plausible BRL
       range (> 0 and < 50,000) to catch obvious parsing errors.

Exit code is non-zero if the schema-validation error rate exceeds
--max-error-rate (default 1%), so this can be used as a CI gate.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from etl.constants import PROCESSED_DIR
from etl.schemas import CheckoutEvent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("etl.validate")

KNOWN_DATASET_START = datetime(2016, 9, 1)
KNOWN_DATASET_END = datetime(2018, 12, 31)
MAX_PLAUSIBLE_BRL = 50_000


def validate_schema(df: pd.DataFrame) -> tuple[int, int, list[dict]]:
    valid = 0
    errors: list[dict] = []
    for row in df.to_dict(orient="records"):
        try:
            CheckoutEvent.model_validate(row)
            valid += 1
        except Exception as exc:  # noqa: BLE001
            errors.append({"transaction_id": row.get("transaction_id"), "error": str(exc)})
    return valid, len(df), errors


def check_uniqueness(df: pd.DataFrame) -> list[str]:
    dupes = df["transaction_id"][df["transaction_id"].duplicated()].unique().tolist()
    return dupes


def check_referential_completeness(df: pd.DataFrame) -> dict[str, int]:
    return {
        col: int(df[col].isna().sum())
        for col in ("order_id", "customer_id", "product_id")
    }


def check_timestamp_range(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(df["timestamp"])
    out_of_range = df[(ts < KNOWN_DATASET_START) | (ts > KNOWN_DATASET_END)]
    return out_of_range


def check_price_sanity(df: pd.DataFrame) -> pd.DataFrame:
    return df[
        (df["unit_price"] <= 0)
        | (df["unit_price"] > MAX_PLAUSIBLE_BRL)
        | (df["total_amount"] > MAX_PLAUSIBLE_BRL)
    ]


def run(input_path: Path, max_error_rate: float) -> bool:
    if not input_path.exists():
        logger.error(
            "Input file not found: %s. Run `python -m etl.preprocess` first.", input_path
        )
        return False

    df = pd.read_parquet(input_path) if input_path.suffix == ".parquet" else pd.read_csv(input_path)
    total = len(df)
    logger.info("Validating %d record(s) from %s", total, input_path)

    valid, total_checked, errors = validate_schema(df)
    error_rate = (len(errors) / total_checked) if total_checked else 0.0
    logger.info("Schema validation: %d/%d valid (%.2f%% error rate)", valid, total_checked, error_rate * 100)
    for e in errors[:10]:
        logger.warning("  INVALID transaction_id=%s: %s", e["transaction_id"], e["error"])

    dupes = check_uniqueness(df)
    if dupes:
        logger.warning("Duplicate transaction_id(s) found: %d -> %s", len(dupes), dupes[:5])
    else:
        logger.info("Uniqueness: OK — no duplicate transaction_id")

    nulls = check_referential_completeness(df)
    if any(nulls.values()):
        logger.warning("Referential completeness: null counts %s", nulls)
    else:
        logger.info("Referential completeness: OK — order_id/customer_id/product_id all populated")

    out_of_range = check_timestamp_range(df)
    if len(out_of_range):
        logger.warning(
            "Timestamp range: %d record(s) outside known Olist window [%s, %s]",
            len(out_of_range),
            KNOWN_DATASET_START.date(),
            KNOWN_DATASET_END.date(),
        )
    else:
        logger.info("Timestamp range: OK — all within known Olist collection window")

    bad_prices = check_price_sanity(df)
    if len(bad_prices):
        logger.warning("Price sanity: %d record(s) with implausible unit_price/total_amount", len(bad_prices))
    else:
        logger.info("Price sanity: OK — all prices within plausible BRL range")

    passed = error_rate <= max_error_rate and not dupes
    logger.info("Overall result: %s", "PASS" if passed else "FAIL")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate processed IceStream checkout events.")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROCESSED_DIR / "checkout_events.parquet",
        help="Path to the processed parquet or csv file to validate.",
    )
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=0.01,
        help="Maximum allowed schema-validation error rate before failing (default 0.01 = 1%%).",
    )
    args = parser.parse_args()

    ok = run(args.input, args.max_error_rate)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
