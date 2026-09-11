from __future__ import annotations

from streaming.producer.config import get_settings


def test_default_settings_match_docker_compose_host_listener():
    settings = get_settings()
    assert settings.kafka_bootstrap_servers == "localhost:29092"
    assert settings.checkout_events_topic == "checkout-events"
    assert settings.checkout_events_dlq_topic == "checkout-events.dlq"
