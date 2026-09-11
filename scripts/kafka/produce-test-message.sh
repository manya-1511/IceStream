#!/usr/bin/env bash
# Publish a single test message to a Kafka topic.
# Usage:
#   bash scripts/kafka/produce-test-message.sh checkout-events '{"hello":"world"}'
#   echo '{"hello":"world"}' | bash scripts/kafka/produce-test-message.sh checkout-events
set -euo pipefail

TOPIC="${1:?Usage: bash scripts/kafka/produce-test-message.sh <topic-name> [message-json]}"
MESSAGE="${2:-}"

if [ -z "${MESSAGE}" ]; then
  if [ -t 0 ]; then
    echo "No message provided and no stdin piped in." >&2
    echo "Usage: bash scripts/kafka/produce-test-message.sh <topic-name> '<json>'" >&2
    exit 1
  fi
  MESSAGE="$(cat)"
fi

echo "${MESSAGE}" | docker exec -i icestream-kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic "${TOPIC}"

echo "Message published to '${TOPIC}'."
