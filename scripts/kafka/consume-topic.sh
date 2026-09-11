#!/usr/bin/env bash
# Console-consume messages from a Kafka topic, for manual inspection.
# Usage:
#   bash scripts/kafka/consume-topic.sh checkout-events
#   bash scripts/kafka/consume-topic.sh checkout-events --from-beginning
#   bash scripts/kafka/consume-topic.sh checkout-events --from-beginning --max-messages 5
set -euo pipefail

TOPIC="${1:?Usage: bash scripts/kafka/consume-topic.sh <topic-name> [--from-beginning] [--max-messages N]}"
shift

EXTRA_ARGS=()
FROM_BEGINNING=""
MAX_MESSAGES=""

while [ $# -gt 0 ]; do
  case "$1" in
    --from-beginning)
      FROM_BEGINNING="--from-beginning"
      shift
      ;;
    --max-messages)
      MAX_MESSAGES="--max-messages $2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

echo "Consuming from topic '${TOPIC}' (Ctrl+C to stop)..."
# shellcheck disable=SC2086
docker exec -it icestream-kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic "${TOPIC}" \
  --property print.key=true \
  --property key.separator=" | " \
  ${FROM_BEGINNING} ${MAX_MESSAGES}
