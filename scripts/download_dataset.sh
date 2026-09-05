#!/usr/bin/env bash
# Downloads the real "Brazilian E-Commerce Public Dataset by Olist" from
# Kaggle into data/raw/olist/.
#
# Requires a Kaggle account and API token (kaggle.json) — this cannot be
# done non-interactively without your credentials, so this script is meant
# to be run on your own machine, not in CI.
#
# Setup (one-time):
#   1. Create a Kaggle account: https://www.kaggle.com
#   2. Go to https://www.kaggle.com/settings/account -> "Create New Token"
#      This downloads kaggle.json.
#   3. Place it at ~/.kaggle/kaggle.json and:  chmod 600 ~/.kaggle/kaggle.json
#      (or export KAGGLE_USERNAME and KAGGLE_KEY as env vars instead)
#
# Usage:
#   bash scripts/download_dataset.sh
set -euo pipefail

DATASET="olistbr/brazilian-ecommerce"
RAW_DIR="data/raw/olist"

if ! command -v kaggle >/dev/null 2>&1; then
  echo "The 'kaggle' CLI is not installed. Install it with:" >&2
  echo "  pip install kaggle --break-system-packages" >&2
  exit 1
fi

if [ ! -f "${HOME}/.kaggle/kaggle.json" ] && [ -z "${KAGGLE_USERNAME:-}" ]; then
  echo "No Kaggle credentials found. See the header of this script for setup steps." >&2
  exit 1
fi

mkdir -p "${RAW_DIR}"
echo "Downloading ${DATASET} into ${RAW_DIR} ..."
kaggle datasets download -d "${DATASET}" -p "${RAW_DIR}" --unzip

echo ""
echo "Done. Expected files in ${RAW_DIR}:"
ls -1 "${RAW_DIR}"

echo ""
echo "Next: run the preprocessing pipeline against the real data:"
echo "  python -m etl.preprocess --raw-dir ${RAW_DIR}"
echo "  python -m etl.validate"
echo "  python -m etl.to_events"
