"""
etl/to_events.py — convert processed canonical records into
streaming-ready events.

Usage:
    python -m etl.to_events
    python -m etl.to_events --input data/processed/checkout_events.parquet \
                             --output data/processed/events/checkout_events.jsonl

Output format: JSON Lines (one CheckoutEvent per line), sorted by
`timestamp` ascending. This is the exact shape and ordering a future
replay engine (Day 3+, not built today — no Kafka yet) will read
sequentially and publish to the `orders.raw` topic at a configurable
rate, so producing it now is what makes the historical dataset
"streaming-ready" without actually standing up Kafka.

Each line is a complete, schema-validated CheckoutEvent — Decimal and
datetime fields are serialized via Pydantic's JSON mode so the output is
directly deserializable by any downstream consumer using the same schema.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from etl.constants import EVENTS_DIR, PROCESSED_DIR
from etl.schemas import CheckoutEvent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("etl.to_events")


def to_jsonl(df: pd.DataFrame, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_sorted = df.sort_values("timestamp").reset_index(drop=True)

    written = 0
    with output_path.open("w", encoding="utf-8") as f:
        for row in df_sorted.to_dict(orient="records"):
            event = CheckoutEvent.model_validate(row)
            f.write(event.model_dump_json())
            f.write("\n")
            written += 1

    return written


def run(input_path: Path, output_path: Path) -> int:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. Run `python -m etl.preprocess` first."
        )
    df = pd.read_parquet(input_path) if input_path.suffix == ".parquet" else pd.read_csv(input_path)
    logger.info("Loaded %d processed record(s) from %s", len(df), input_path)

    count = to_jsonl(df, output_path)
    logger.info("Wrote %d streaming-ready event(s) to %s", count, output_path)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert processed checkout events into ordered, streaming-ready JSON Lines."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROCESSED_DIR / "checkout_events.parquet",
        help="Processed parquet or csv file produced by etl.preprocess.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=EVENTS_DIR / "checkout_events.jsonl",
        help="Output JSON Lines path.",
    )
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
