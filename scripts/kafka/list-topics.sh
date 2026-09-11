#!/usr/bin/env bash
# List all Kafka topics.
# Usage: bash scripts/kafka/list-topics.sh
set -euo pipefail

docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --list
