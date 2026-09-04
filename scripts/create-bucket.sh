#!/bin/sh
# Idempotent MinIO warehouse bucket bootstrap for IceStream.
set -eu

mc alias set local http://minio:9000 "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}"
mc mb --ignore-existing "local/${MINIO_BUCKET}"
echo "Bucket ready: ${MINIO_BUCKET}"
mc ls local
