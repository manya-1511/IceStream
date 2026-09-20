"""
IceStream monitored streaming engine — Day 3.

Same real-data replay as streaming/run_stream.py (Day 2), but every record
also passes through the Day 3 monitoring layer:

    receive -> validate -> quality check -> anomaly detection ->
        normal storage OR quarantine -> (if needed) recovery

Records are grouped into time windows (default 10s). At the end of each
window, the circuit breaker checks for an error-rate or volume anomaly; if
one is found, an incident is opened and the circuit "trips" — new records
are held in quarantine until an automatic recovery attempt succeeds.

Day 2's streaming/run_stream.py is untouched and still works exactly as
before (no monitoring) — this is a separate, additive entrypoint.

Usage:
    python streaming/run_monitored_stream.py --rate 10
    python streaming/run_monitored_stream.py --rate 10 --window-seconds 10 --error-threshold 5
    python streaming/run_monitored_stream.py --rate 20 --limit 2000 --truncate
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from reader import read_orders, DEFAULT_SOURCE
import db as streaming_db

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "quality"))
from engine import QualityEngine  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "monitoring"))
from pipeline import MonitoredPipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IceStream monitored streaming engine (Day 3)")
    parser.add_argument("--rate", type=float, default=10.0, help="Approximate records/sec (default: 10)")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Processed CSV to replay")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N records")
    parser.add_argument("--truncate", action="store_true", help="Empty valid_orders/quarantine_orders first")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-record [QUALITY] logs")
    parser.add_argument(
        "--window-seconds", type=float, default=10.0,
        help="Monitoring window size in seconds (default: 10)",
    )
    parser.add_argument(
        "--error-threshold", type=float, default=5.0,
        help="Error rate %% that triggers an incident (default: 5.0)",
    )
    parser.add_argument(
        "--volume-multiplier", type=float, default=3.0,
        help="Records/sec must exceed this multiple of the recent baseline to trigger a volume incident (default: 3.0)",
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

    pipeline = MonitoredPipeline(
        engine=engine,
        quality_engine=quality_engine,
        source=args.source,
        window_seconds=args.window_seconds,
        error_threshold=args.error_threshold,
        volume_multiplier=args.volume_multiplier,
        quiet=args.quiet,
    )

    interval = 1.0 / args.rate
    print(f"[STREAM] Starting monitored replay of {args.source} at ~{args.rate} records/sec")
    print(f"[STREAM] window={args.window_seconds}s error_threshold={args.error_threshold}%")
    if args.limit:
        print(f"[STREAM] Limited to {args.limit:,} records")

    try:
        for raw_row in read_orders(source=args.source, limit=args.limit):
            tick_start = time.monotonic()

            if not args.quiet:
                print(
                    f"[STREAM] Record received | invoice={raw_row.get('invoice_no')} "
                    f"stock={raw_row.get('stock_code')} qty={raw_row.get('quantity')} "
                    f"price={raw_row.get('unit_price')}"
                )

            pipeline.handle_raw_row(raw_row)

            elapsed = time.monotonic() - tick_start
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\n[STREAM] Stopped by user (Ctrl+C)")

    pipeline.finalize()

    print("\n===== Run Summary =====")
    print(f"Total records         : {pipeline.total:,}")
    print(f"Valid records         : {pipeline.valid_count:,}")
    print(f"Invalid records       : {pipeline.invalid_count:,}")
    print(f"Held by open circuit  : {pipeline.held_by_circuit:,}")
    print(f"Final circuit state   : {pipeline.circuit.state.value}")
    print("========================\n")


if __name__ == "__main__":
    main()
