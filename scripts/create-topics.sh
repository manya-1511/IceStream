#!/usr/bin/env bash
# Idempotent Kafka topic bootstrap for IceStream.
# Safe to run multiple times — uses --if-not-exists.
set -euo pipefail

BOOTSTRAP_SERVER="kafka:9092"
TOPICS=(
  "orders.raw"
  "orders.valid"
  "orders.invalid"
  "orders.dlq"
  "schema.events"
  "quality.events"
  "incidents"
)

echo "Waiting for Kafka to accept connections at ${BOOTSTRAP_SERVER}..."
until /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server "${BOOTSTRAP_SERVER}" >/dev/null 2>&1; do
  sleep 2
done

for topic in "${TOPICS[@]}"; do
  echo "Ensuring topic exists: ${topic}"
  /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "${BOOTSTRAP_SERVER}" \
    --create \
    --if-not-exists \
    --topic "${topic}" \
    --partitions 3 \
    --replication-factor 1
done

echo "Topic bootstrap complete. Current topics:"
/opt/kafka/bin/kafka-topics.sh --bootstrap-server "${BOOTSTRAP_SERVER}" --list
