#!/usr/bin/env bash
# Show consumer group lag (how far behind a consumer group is).
# Usage:
#   bash scripts/kafka/consumer-lag.sh                        # list all groups
#   bash scripts/kafka/consumer-lag.sh icestream-flink-jobs    # describe one group
set -euo pipefail

GROUP="${1:-}"

if [ -z "${GROUP}" ]; then
  echo "No group specified — listing all consumer groups:"
  docker exec icestream-kafka /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 \
    --list
  echo ""
  echo "Run again with a group name to see its lag, e.g.:"
  echo "  bash scripts/kafka/consumer-lag.sh <group-name>"
else
  docker exec icestream-kafka /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 \
    --describe \
    --group "${GROUP}"
fi
