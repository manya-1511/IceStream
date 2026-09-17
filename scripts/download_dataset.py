"""
Download the real "Online Retail II" dataset from the UCI Machine Learning
Repository and save it into data/raw/.

Source : https://archive.ics.uci.edu/dataset/502/online+retail+ii
License: Creative Commons Attribution 4.0 International (CC BY 4.0)
"""

import io
import sys
import zipfile
from pathlib import Path

import requests

DATASET_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading dataset from:\n  {DATASET_URL}")
    try:
        response = requests.get(DATASET_URL, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"ERROR: could not download dataset: {exc}", file=sys.stderr)
        print(
            "If your network blocks archive.ics.uci.edu, download the ZIP "
            "manually from the URL above and place its contents in data/raw/.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Downloaded {len(response.content):,} bytes. Extracting...")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        zf.extractall(RAW_DIR)
        extracted = zf.namelist()

    print(f"Extracted {len(extracted)} file(s) into {RAW_DIR}:")
    for name in extracted:
        print(f"  - {name}")

    print("\nDone. Next step: python scripts/preprocess_data.py")


if __name__ == "__main__":
    main()
