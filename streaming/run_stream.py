"""
IceStream streaming engine — Day 2.

Replays the REAL processed dataset (data/processed/orders_clean.csv) as a
simulated real-time order stream: rows are emitted in their original
invoice_date order, at an approximate target rate, and each one goes
through:

    receive -> validate -> quality check -> store

Usage:
    python streaming/run_stream.py --rate 10
    python streaming/run_stream.py --rate 50 --limit 2000
    python streaming/run_stream.py --rate 100 --truncate

Run this from the project root (so the default data path resolves), or
from anywhere using --source to point at the CSV explicitly.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

# Local, same-directory modules (Python auto-adds this script's folder to sys.path)
from reader import read_orders, DEFAULT_SOURCE
from validator import validate_record, EMPTY_TYPED_RECORD, raw_to_jsonable
import db as streaming_db

# quality/ is a sibling package, not on sys.path by default
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "quality"))
from engine import QualityEngine  # noqa: E402
from metrics import compute_metrics, format_metrics  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IceStream real-time streaming engine")
    parser.add_argument(
        "--rate", type=float, default=10.0,
        help="Approximate records per second to emit (default: 10)",
    )
    parser.add_argument(
        "--source", type=Path, default=DEFAULT_SOURCE,
        help="Path to the processed CSV to replay (default: data/processed/orders_clean.csv)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Stop after this many records (default: stream the whole dataset)",
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="Empty valid_orders and quarantine_orders before starting",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Only print the final metrics summary, not per-record logs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.rate <= 0:
        print("ERROR: --rate must be greater than 0", file=sys.stderr)
        sys.exit(1)

    engine = streaming_db.get_engine()

    if args.truncate:
        streaming_db.truncate_pipeline_tables(engine)
        print("[DATABASE] Truncated valid_orders and quarantine_orders")

    quality_engine = QualityEngine()
    loaded = quality_engine.preload_seen_keys(streaming_db.preload_seen_keys(engine))
    if loaded:
        print(f"[QUALITY] Preloaded {loaded:,} existing line-item keys for duplicate detection")

    interval = 1.0 / args.rate
    total = 0
    valid_count = 0
    invalid_count = 0
    rule_failures: Counter[str] = Counter()

    print(f"[STREAM] Starting replay of {args.source} at ~{args.rate} records/sec")
    if args.limit:
        print(f"[STREAM] Limited to {args.limit:,} records")

    try:
        for raw_row in read_orders(source=args.source, limit=args.limit):
            tick_start = time.monotonic()
            total += 1

            if not args.quiet:
                print(
                    f"[STREAM] Record received | invoice={raw_row.get('invoice_no')} "
                    f"stock={raw_row.get('stock_code')} qty={raw_row.get('quantity')} "
                    f"price={raw_row.get('unit_price')}"
                )

            record, parse_error = validate_record(raw_row)

            if parse_error:
                invalid_count += 1
                rule_failures["PARSE_ERROR"] += 1
                if not args.quiet:
                    print(f"[QUALITY] Failed: {parse_error} (rule=PARSE_ERROR)")
                streaming_db.store_quarantine(
                    engine,
                    typed_record=EMPTY_TYPED_RECORD,
                    raw_record=raw_to_jsonable(raw_row),
                    rule="PARSE_ERROR",
                    reason=parse_error,
                )
                if not args.quiet:
                    print("[DATABASE] Stored -> quarantine_orders")
            else:
                result = quality_engine.check(record)
                if result.valid:
                    valid_count += 1
                    if not args.quiet:
                        print("[QUALITY] Passed")
                    streaming_db.store_valid(engine, record)
                    quality_engine.mark_seen(record)
                    if not args.quiet:
                        print("[DATABASE] Stored -> valid_orders")
                else:
                    invalid_count += 1
                    rule_failures[result.rule] += 1
                    if not args.quiet:
                        print(f"[QUALITY] Failed: {result.reason} (rule={result.rule})")
                    streaming_db.store_quarantine(
                        engine,
                        typed_record=record,
                        raw_record=record,
                        rule=result.rule,
                        reason=result.reason,
                    )
                    if not args.quiet:
                        print("[DATABASE] Stored -> quarantine_orders")

            elapsed = time.monotonic() - tick_start
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\n[STREAM] Stopped by user (Ctrl+C)")

    metrics = compute_metrics(total, valid_count, invalid_count)
    print(format_metrics(metrics))

    if rule_failures:
        print("Failures by rule:")
        for rule, count in rule_failures.most_common():
            print(f"  - {rule}: {count:,}")


if __name__ == "__main__":
    main()
