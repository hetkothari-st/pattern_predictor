"""Train the 1D-CNN with auto-generated labels.

Workflow:
  1. Read OHLCV CSV files (the user supplies them; one symbol per file).
  2. Slide the rule detectors over every history; whenever a detector fires
     with status='completed', capture the trailing WINDOW bars as a positive
     example for that pattern's class. Capture the truncated version of the
     same window as an early-warning positive.
  3. Sample random "none" windows from gaps between detections.
  4. Train, val-split, save to settings.model_path.

Usage:
    python -m app.ml.train --data data/ohlcv/*.csv --epochs 20
"""
from __future__ import annotations

import argparse
import glob
import logging
import random
from pathlib import Path

import numpy as np

from ..config import settings
from ..detectors.registry import REGISTRY
from ..messages import Bar
from .model import PATTERN_CLASSES, build_model
from .windows import WINDOW, bars_to_window, early_window

log = logging.getLogger("train")


def load_csv(path: Path) -> list[Bar]:
    """Expects columns: ts, open, high, low, close, volume."""
    import pandas as pd

    df = pd.read_csv(path)
    bars: list[Bar] = []
    sym = path.stem
    for _, row in df.iterrows():
        bars.append(
            Bar(
                symbol=sym,
                tf="1m",
                ts=float(row["ts"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
                closed=True,
            )
        )
    return bars


def auto_label(bars: list[Bar]) -> list[tuple[np.ndarray, np.ndarray, int]]:
    """Return list of (full_window, early_window, class_index).

    Walks the history, runs all detectors at each step, and harvests positives.
    For every positive, also samples a "none" window from a quiet region.
    """
    cls_idx = {name: i for i, name in enumerate(PATTERN_CLASSES)}
    out: list[tuple[np.ndarray, np.ndarray, int]] = []
    n = len(bars)
    if n < WINDOW + 50:
        return out
    seen: set[tuple[str, float, float]] = set()
    for end in range(WINDOW + 50, n, 5):  # step every 5 bars
        window = bars[:end]
        for det_cls in REGISTRY:
            for d in det_cls().detect(window):
                if d.status != "completed":
                    continue
                key = (d.pattern, d.start_ts, d.end_ts)
                if key in seen:
                    continue
                seen.add(key)
                full = bars_to_window(window)
                early = early_window(window)
                if full is None or early is None:
                    continue
                idx = cls_idx.get(d.pattern, 0)
                out.append((full, early, idx))
        # Periodic "none" sample.
        if end % 200 == 0:
            full = bars_to_window(window)
            early = early_window(window)
            if full is not None and early is not None:
                out.append((full, early, 0))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True, help="CSV globs of OHLCV history")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()

    paths: list[Path] = []
    for g in args.data:
        paths.extend(Path(p) for p in glob.glob(g))
    if not paths:
        raise SystemExit("No CSV files matched.")

    samples: list[tuple[np.ndarray, np.ndarray, int]] = []
    for p in paths:
        log.info("Labelling %s", p)
        bars = load_csv(p)
        samples.extend(auto_label(bars))
    if not samples:
        raise SystemExit("Detectors produced no positives; check input data quality.")
    log.info("Total samples: %d", len(samples))

    import torch
    from torch.utils.data import DataLoader, TensorDataset

    full = np.stack([s[0] for s in samples])
    early = np.stack([s[1] for s in samples])
    y = np.array([s[2] for s in samples], dtype=np.int64)
    perm = np.random.permutation(len(y))
    full, early, y = full[perm], early[perm], y[perm]
    split = int(0.85 * len(y))

    def make_loader(start: int, end: int) -> DataLoader:
        ds = TensorDataset(
            torch.from_numpy(full[start:end]),
            torch.from_numpy(early[start:end]),
            torch.from_numpy(y[start:end]),
        )
        return DataLoader(ds, batch_size=args.batch, shuffle=(start == 0))

    train_dl = make_loader(0, split)
    val_dl = make_loader(split, len(y))

    model = build_model()
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    loss_fn = torch.nn.CrossEntropyLoss()
    best_val = float("inf")
    out_path = Path(settings.model_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(args.epochs):
        model.train()
        for xb, xe, yb in train_dl:
            opt.zero_grad()
            pat_logits, early_logits = model(xb)
            _, early_l = model(xe)
            loss = 0.5 * loss_fn(pat_logits, yb) + 0.5 * loss_fn(early_l, yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            losses = []
            for xb, xe, yb in val_dl:
                pat_logits, _ = model(xb)
                losses.append(loss_fn(pat_logits, yb).item())
            val = float(np.mean(losses)) if losses else float("inf")
        log.info("epoch %d val_loss=%.4f", epoch, val)
        if val < best_val:
            best_val = val
            torch.save(model.state_dict(), out_path)
            log.info("saved %s", out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
