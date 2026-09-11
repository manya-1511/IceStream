#!/usr/bin/env bash
# Describe a Kafka topic (partitions, replicas, config).
# Usage: bash scripts/kafka/describe-topic.sh checkout-events
set -euo pipefail

TOPIC="${1:?Usage: bash scripts/kafka/describe-topic.sh <topic-name>}"

docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --topic "${TOPIC}"
