"""Nightly retrain: pull historical CSVs + recent outcome-weighted samples,
call the trainer, promote the new checkpoint if val improves.

Invoke from cron / a workflow runner:
    python -m app.learning.retrain --data data/ohlcv/*.csv
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys

log = logging.getLogger("retrain")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    args = ap.parse_args()
    # Promotion logic lives in train.py (it only writes a checkpoint when val
    # improves). We just forward.
    cmd = [sys.executable, "-m", "app.ml.train", "--data", *args.data]
    log.info("running %s", " ".join(cmd))
    subprocess.check_call(cmd)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
