"""Configuration for the checkout-events Kafka producer.

Reads from environment variables / a local .env file, with defaults that
work out of the box against docker-compose.yml's Kafka HOST listener
(localhost:29092) — see streaming/producer/.env.example.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from etl.constants import EVENTS_DIR

DEFAULT_INPUT_PATH = EVENTS_DIR / "checkout_events.jsonl"


class ProducerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    kafka_bootstrap_servers: str = "localhost:29092"
    checkout_events_topic: str = "checkout-events"
    checkout_events_dlq_topic: str = "checkout-events.dlq"


def get_settings() -> ProducerSettings:
    return ProducerSettings()
