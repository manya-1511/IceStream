from __future__ import annotations

from pathlib import Path

from streaming.producer.cli import build_parser, main


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.mode == "fixed-rate"
    assert args.events_per_second == 10.0
    assert args.replay_speed == 60.0
    assert args.max_records is None
    assert args.loop is False
    assert args.dry_run is False
    assert args.topic == "checkout-events"
    assert args.dlq_topic == "checkout-events.dlq"


def test_parser_accepts_all_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--input",
            "some/file.jsonl",
            "--bootstrap-servers",
            "example:9092",
            "--topic",
            "custom-topic",
            "--dlq-topic",
            "custom-topic.dlq",
            "--mode",
            "replay",
            "--replay-speed",
            "30",
            "--max-records",
            "100",
            "--loop",
            "--log-interval-seconds",
            "1",
            "--dry-run",
        ]
    )
    assert args.input == Path("some/file.jsonl")
    assert args.bootstrap_servers == "example:9092"
    assert args.topic == "custom-topic"
    assert args.dlq_topic == "custom-topic.dlq"
    assert args.mode == "replay"
    assert args.replay_speed == 30.0
    assert args.max_records == 100
    assert args.loop is True
    assert args.log_interval_seconds == 1.0
    assert args.dry_run is True


def test_main_dry_run_end_to_end_exits_zero(sample_jsonl: Path, capsys):
    exit_code = main(
        [
            "--dry-run",
            "--input",
            str(sample_jsonl),
            "--events-per-second",
            "1000",
        ]
    )
    assert exit_code == 0


def test_main_dry_run_with_dlq_records_still_exits_zero(jsonl_with_bad_record: Path):
    """Records failing schema validation are handled (routed to DLQ), not
    a fatal error -- exit code should still be success."""
    exit_code = main(
        [
            "--dry-run",
            "--input",
            str(jsonl_with_bad_record),
            "--events-per-second",
            "1000",
        ]
    )
    assert exit_code == 0


def test_main_missing_input_file_exits_nonzero(tmp_path: Path):
    exit_code = main(
        [
            "--dry-run",
            "--input",
            str(tmp_path / "missing.jsonl"),
        ]
    )
    assert exit_code == 1
