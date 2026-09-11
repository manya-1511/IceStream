"""
streaming/producer/cli.py -- command-line entrypoint for the checkout-
events Kafka producer.

Examples:
    # Dry run against the Day 2 sample data, no Kafka required:
    python -m streaming.producer.cli --dry-run --input data/samples/checkout_events_sample.jsonl

    # Publish the full processed dataset at a fixed 10 events/sec:
    python -m streaming.producer.cli --events-per-second 10

    # Replay preserving real relative timing, sped up 60x:
    python -m streaming.producer.cli --mode replay --replay-speed 60

    # Publish only the first 5 records, looping forever:
    python -m streaming.producer.cli --max-records 5 --loop
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from streaming.producer.config import DEFAULT_INPUT_PATH, get_settings
from streaming.producer.replay import DryRunEventSender, KafkaEventSender, run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("streaming.producer.cli")


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Publish IceStream checkout events to Kafka's checkout-events topic."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"JSON Lines file of checkout events to publish (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=settings.kafka_bootstrap_servers,
        help=f"Kafka bootstrap servers (default: {settings.kafka_bootstrap_servers})",
    )
    parser.add_argument(
        "--topic",
        default=settings.checkout_events_topic,
        help=f"Target topic for valid events (default: {settings.checkout_events_topic})",
    )
    parser.add_argument(
        "--dlq-topic",
        default=settings.checkout_events_dlq_topic,
        help=f"Target topic for events that fail schema validation (default: {settings.checkout_events_dlq_topic})",
    )
    parser.add_argument(
        "--mode",
        choices=["fixed-rate", "replay"],
        default="fixed-rate",
        help=(
            "fixed-rate: send at --events-per-second. "
            "replay: preserve real relative timestamp gaps, scaled by --replay-speed."
        ),
    )
    parser.add_argument(
        "--events-per-second",
        type=float,
        default=10.0,
        help="Target send rate in fixed-rate mode (default: 10.0)",
    )
    parser.add_argument(
        "--replay-speed",
        type=float,
        default=60.0,
        help="Speed-up factor in replay mode; 60 = 1 hour of source time plays out in 1 minute (default: 60.0)",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Only publish the first N records (default: all records in the input file)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop over the input file indefinitely instead of stopping after one pass",
    )
    parser.add_argument(
        "--log-interval-seconds",
        type=float,
        default=5.0,
        help="How often to log throughput, in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't connect to Kafka at all -- just log what would be sent. Useful without a running broker.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.dry_run:
        logger.info("Running in DRY-RUN mode -- no connection to Kafka will be made.")
        sender = DryRunEventSender()
    else:
        logger.info("Connecting to Kafka at %s", args.bootstrap_servers)
        try:
            sender = KafkaEventSender(args.bootstrap_servers)
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not connect to Kafka at %s: %s", args.bootstrap_servers, exc)
            logger.error("Is the broker running? Try: docker compose ps kafka")
            logger.error("Or run with --dry-run to test without a broker.")
            return 1

    try:
        stats = run(
            input_path=args.input,
            sender=sender,
            topic=args.topic,
            dlq_topic=args.dlq_topic,
            mode=args.mode,
            events_per_second=args.events_per_second,
            replay_speed=args.replay_speed,
            max_records=args.max_records,
            loop=args.loop,
            log_interval_seconds=args.log_interval_seconds,
        )
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1
    finally:
        sender.close()

    if args.dry_run:
        logger.info("Dry run complete -- %d message(s) would have been sent.", len(sender.sent))

    return 0 if stats.parse_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
