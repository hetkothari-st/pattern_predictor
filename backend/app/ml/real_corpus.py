"""Mine real OHLCV CSVs for labeled training windows.

Walks each CSV bar-by-bar; whenever a rule detector emits a `completed`
event, snip the trailing WINDOW bars and tag them with that pattern's class.
Periodically samples WINDOW windows from quiet stretches and tags them
`none`.

The rule detector's bias seeps in (it's the labeler), but on real bars at
least the SHAPES are real — random walks of the synth corpus alone don't
teach the model what genuine market noise looks like. Best of both worlds:
mix this with the synth corpus.

Usage:
    python -m app.ml.real_corpus --data "../data/ohlcv/NIFTY50_*.csv" --out ../data/ml/real.npz
"""
from __future__ import annotations

import argparse
import glob
import logging
from pathlib import Path

import numpy as np

from ..detectors.registry import REGISTRY
from ..messages import Bar
from ..ml.train import load_csv
from .model import PATTERN_CLASSES
from .windows import WINDOW, bars_to_window, early_window

log = logging.getLogger("real_corpus")


def mine(bars: list[Bar], step: int = 5) -> tuple[list[np.ndarray], list[np.ndarray], list[int]]:
    cls_idx = {n: i for i, n in enumerate(PATTERN_CLASSES)}
    Xf, Xe, y = [], [], []
    n = len(bars)
    if n < WINDOW + 30:
        return Xf, Xe, y
    seen: set[tuple[str, float, float]] = set()
    for end in range(WINDOW + 30, n, step):
        window = bars[:end]
        recent = window[-WINDOW:]
        labelled = False
        for det_cls in REGISTRY:
            try:
                detections = det_cls().detect(window)
            except Exception:
                continue
            for d in detections:
                if d.status != "completed":
                    continue
                key = (d.pattern, d.start_ts, d.end_ts)
                if key in seen:
                    continue
                seen.add(key)
                full = bars_to_window(recent)
                early = early_window(recent)
                if full is None or early is None:
                    continue
                Xf.append(full)
                Xe.append(early)
                y.append(cls_idx.get(d.pattern, 0))
                labelled = True
        if not labelled and end % 200 == 0:
            full = bars_to_window(recent)
            early = early_window(recent)
            if full is not None and early is not None:
                Xf.append(full)
                Xe.append(early)
                y.append(cls_idx["none"])
    return Xf, Xe, y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="CSV glob")
    ap.add_argument("--out", default="../data/ml/real.npz")
    ap.add_argument("--step", type=int, default=5)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    paths = sorted(Path(p) for p in glob.glob(args.data))
    if not paths:
        raise SystemExit(f"no CSV matched: {args.data}")

    Xf, Xe, y = [], [], []
    for p in paths:
        log.info("mining %s", p.name)
        bars = load_csv(p)
        a, b, c = mine(bars, step=args.step)
        log.info("  %d samples", len(c))
        Xf.extend(a)
        Xe.extend(b)
        y.extend(c)

    if not y:
        raise SystemExit("no samples mined; check input data")
    Xf_arr = np.stack(Xf).astype(np.float32)
    Xe_arr = np.stack(Xe).astype(np.float32)
    y_arr = np.array(y, dtype=np.int64)
    log.info("class counts: %s",
             dict(zip(PATTERN_CLASSES, np.bincount(y_arr, minlength=len(PATTERN_CLASSES)).tolist())))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, X_full=Xf_arr, X_early=Xe_arr, y=y_arr)
    log.info("wrote %d real samples to %s", len(y_arr), out)


if __name__ == "__main__":
    main()
