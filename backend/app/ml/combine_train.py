"""Combine synth + real npz into one corpus, then run train_v2.

The real corpus pulls SHAPES from real bars (volatility, gaps, intraday
asymmetry the synth never produces) but inherits rule-detector label noise.
The synth corpus has clean labels but textbook geometry. Mixing both gives
the model real-market noise patterns AND grounded labels.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import numpy as np

log = logging.getLogger("combine_train")


def merge(synth_path: Path, real_path: Path, out_path: Path, real_weight: float = 1.0) -> None:
    s = np.load(synth_path)
    r = np.load(real_path)
    log.info("synth: %d samples, real: %d samples", len(s["y"]), len(r["y"]))

    # Up/down-weight real samples by repeating them.
    repeats = max(1, int(round(real_weight)))
    Xf = np.concatenate([s["X_full"]] + [r["X_full"]] * repeats, axis=0)
    Xe = np.concatenate([s["X_early"]] + [r["X_early"]] * repeats, axis=0)
    y = np.concatenate([s["y"]] + [r["y"]] * repeats, axis=0)
    log.info("combined: %d samples (real weighted x%d)", len(y), repeats)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, X_full=Xf, X_early=Xe, y=y)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synth", default="../data/ml/corpus.npz")
    ap.add_argument("--real", default="../data/ml/real.npz")
    ap.add_argument("--out", default="../data/ml/combined.npz")
    ap.add_argument("--real-weight", type=float, default=1.0,
                    help="repeat real samples this many times in the merge")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--no-train", action="store_true",
                    help="just merge, don't kick off train_v2")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    merge(Path(args.synth), Path(args.real), Path(args.out), real_weight=args.real_weight)

    if args.no_train:
        return

    backend_root = Path(__file__).resolve().parent.parent.parent
    cmd = [
        sys.executable, "-m", "app.ml.train_v2",
        "--npz", args.out,
        "--epochs", str(args.epochs),
        "--patience", str(args.patience),
    ]
    log.info("running %s", " ".join(cmd))
    subprocess.check_call(cmd, cwd=backend_root)


if __name__ == "__main__":
    main()
