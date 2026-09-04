#!/usr/bin/env bash
# Checks whether every IceStream Day-1 service is reachable from the host.
# Does NOT fake results — each check actually hits the service.
set -uo pipefail

PASS=0
FAIL=0

check() {
  local name="$1"
  local cmd="$2"
  printf "%-28s" "${name}"
  if eval "${cmd}" >/dev/null 2>&1; then
    echo "OK"
    PASS=$((PASS + 1))
  else
    echo "FAIL"
    FAIL=$((FAIL + 1))
  fi
}

check "FastAPI /"                "curl -sf http://localhost:8000/"
check "FastAPI /health"          "curl -sf http://localhost:8000/health"
check "React frontend"           "curl -sf http://localhost:5173/"
check "Flink Web UI"             "curl -sf http://localhost:8081/overview"
check "MinIO console"            "curl -sf http://localhost:9001/"
check "MinIO S3 API"             "curl -sf http://localhost:9000/minio/health/live"
check "PostgreSQL (via docker)"  "docker exec icestream-postgres pg_isready -U \${POSTGRES_USER:-icestream}"
check "Redis (via docker)"       "docker exec icestream-redis redis-cli ping"
check "Kafka (via docker)"       "docker exec icestream-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server kafka:9092"

echo ""
echo "Passed: ${PASS}  Failed: ${FAIL}"
[ "${FAIL}" -eq 0 ]
