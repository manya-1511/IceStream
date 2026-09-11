#!/usr/bin/env bash
# Idempotent Kafka topic bootstrap for IceStream.
# Safe to run multiple times — uses --if-not-exists.
#
# NOTE (Day 3): "checkout-events" and "checkout-events.dlq" replace the
# Day 1 placeholder names "orders.raw" and "orders.dlq". Day 1 predates
# the canonical CheckoutEvent schema (finalized on Day 2), so those two
# names were provisional and unused by any producer/consumer. The other
# Day 1 placeholder topics (orders.valid, orders.invalid, schema.events,
# quality.events, incidents) are kept as-is — they still represent real
# future pipeline stages (Flink validation output, the quality engine,
# incident management) that Day 3 does not touch.
set -euo pipefail

BOOTSTRAP_SERVER="kafka:9092"

# topic:partitions:replication-factor
TOPIC_SPECS=(
  "checkout-events:6:1"        # active — published to by the Day 3 producer
  "checkout-events.dlq:3:1"    # active — events that fail schema validation
  "orders.valid:3:1"           # reserved for a future Flink validation stage
  "orders.invalid:3:1"         # reserved for a future Flink validation stage
  "schema.events:3:1"          # reserved for future schema-change tracking
  "quality.events:3:1"         # reserved for the future data-quality engine
  "incidents:3:1"              # reserved for future incident management
)

echo "Waiting for Kafka to accept connections at ${BOOTSTRAP_SERVER}..."
until /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server "${BOOTSTRAP_SERVER}" >/dev/null 2>&1; do
  sleep 2
done

for spec in "${TOPIC_SPECS[@]}"; do
  IFS=':' read -r topic partitions replication <<< "${spec}"
  echo "Ensuring topic exists: ${topic} (partitions=${partitions}, replication-factor=${replication})"
  /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "${BOOTSTRAP_SERVER}" \
    --create \
    --if-not-exists \
    --topic "${topic}" \
    --partitions "${partitions}" \
    --replication-factor "${replication}"
done

echo ""
echo "Topic bootstrap complete. Current topics:"
/opt/kafka/bin/kafka-topics.sh --bootstrap-server "${BOOTSTRAP_SERVER}" --list
