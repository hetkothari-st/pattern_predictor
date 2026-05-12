"""Generate a directly-labeled training corpus from `tests/synth.py`.

Each sample is one `(WINDOW, CHANNELS)` array with its true class label.
We do NOT round-trip through CSV files + auto-labeling — the rule detector's
biases were poisoning the training set (anything vaguely with two peaks
became `double_top`, etc).

Two output modes:

1. `--out-csv DIR`: write per-pattern CSVs (kept for backwards-compat with
   `app.ml.train`).
2. `--out-npz FILE` (recommended): write a single .npz with `X_full`, `X_early`,
   `y` arrays — `app.ml.train_v2` reads this directly with no labelling step.

Augmentation per sample:
- Random base price level + scale
- Time stretch (resample to a random length, then center inside WINDOW)
- Amplitude jitter on each bar's mid-price
- Realistic OHLC envelope with random direction
- Random pre/post padding with a calm random walk so the model learns to find
  the pattern in a longer noisy context
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import synth  # type: ignore  # noqa: E402

from ..messages import Bar  # noqa: E402
from .model import PATTERN_CLASSES  # noqa: E402
from .windows import CHANNELS, WINDOW, bars_to_window, early_window  # noqa: E402

PATTERN_FACTORIES: dict[str, Callable[[], list[Bar]]] = {
    "head_and_shoulders": synth.head_and_shoulders,
    "inverse_head_and_shoulders": synth.inverse_head_and_shoulders,
    "double_top": synth.double_top,
    "double_bottom": synth.double_bottom,
    "ascending_triangle": synth.ascending_triangle,
    "descending_triangle": synth.descending_triangle,
    "symmetric_triangle": synth.symmetric_triangle,
    "rising_wedge": synth.rising_wedge,
    "falling_wedge": synth.falling_wedge,
    "bull_flag": synth.bull_flag,
    "bear_flag": synth.bear_flag,
    "cup_with_handle": synth.cup_with_handle,
}


def _enrich(bars: list[Bar], rng: random.Random, vol: float) -> list[Bar]:
    out = []
    for b in bars:
        body = vol * 0.6
        wick = vol
        direction = 1 if rng.random() < 0.5 else -1
        open_ = b.close - direction * body * 0.4
        close_ = b.close + direction * body * 0.6
        out.append(
            Bar(
                symbol=b.symbol,
                tf=b.tf,
                ts=b.ts,
                open=open_,
                high=max(open_, close_) + wick * rng.uniform(0.4, 1.4),
                low=min(open_, close_) - wick * rng.uniform(0.4, 1.4),
                close=close_,
                volume=rng.uniform(50, 500),
                closed=True,
            )
        )
    return out


def _time_stretch(bars: list[Bar], target_n: int) -> list[Bar]:
    """Linear-interpolate the close series to a new length, preserving shape."""
    if len(bars) == target_n:
        return bars
    src = np.array([b.close for b in bars], dtype=np.float64)
    src_x = np.linspace(0, 1, len(src))
    dst_x = np.linspace(0, 1, target_n)
    new_close = np.interp(dst_x, src_x, src)
    out = []
    for i, c in enumerate(new_close):
        out.append(
            Bar(
                symbol=bars[0].symbol,
                tf=bars[0].tf,
                ts=float(i * 60),
                open=float(c),
                high=float(c),
                low=float(c),
                close=float(c),
                volume=1.0,
                closed=True,
            )
        )
    return out


def _calm_walk(n: int, anchor: float, rng: random.Random, sigma: float) -> list[Bar]:
    bars = []
    p = anchor
    for i in range(n):
        p += rng.gauss(0, sigma) + (anchor - p) * 0.02
        bars.append(
            Bar(symbol="pad", tf="1m", ts=float(i * 60),
                open=p, high=p, low=p, close=p, volume=1.0, closed=True)
        )
    return bars


def _vary_pattern(bars: list[Bar], rng: random.Random) -> list[Bar]:
    """Apply price-level shift, scale, and time-stretch."""
    closes = np.array([b.close for b in bars])
    centre = closes.mean()
    base_level = rng.uniform(80.0, 30000.0)
    scale = rng.uniform(0.7, 1.4)
    target_len = max(40, min(WINDOW - 20, int(len(bars) * rng.uniform(0.7, 1.3))))
    stretched = _time_stretch(bars, target_len)
    out = []
    for b in stretched:
        new_close = base_level + (b.close - centre) * scale
        out.append(
            Bar(
                symbol=b.symbol,
                tf=b.tf,
                ts=b.ts,
                open=new_close,
                high=new_close,
                low=new_close,
                close=new_close,
                volume=b.volume,
                closed=True,
            )
        )
    return out


def _pad_into_window(pattern_bars: list[Bar], rng: random.Random) -> list[Bar]:
    """Surround the pattern with calm random-walk padding so the network
    learns to localise. Pattern goes anywhere in the window; ends with
    enough room that the bars[-1] sometimes sits at the pattern tip
    (forming) and sometimes after it (already broken)."""
    n = len(pattern_bars)
    pad_total = WINDOW - n
    # Bias pattern toward right side so most samples end "inside or just after" the pattern.
    pre = rng.randint(max(0, pad_total // 4), max(1, pad_total - 5))
    post = pad_total - pre
    sigma = abs(pattern_bars[0].close) * 0.001
    pre_bars = _calm_walk(pre, pattern_bars[0].close, rng, sigma) if pre > 0 else []
    post_bars = _calm_walk(post, pattern_bars[-1].close, rng, sigma) if post > 0 else []
    full = pre_bars + pattern_bars + post_bars
    # Re-time and renormalise volume noise.
    out = []
    vol_scale = abs(pattern_bars[0].close) * rng.uniform(0.0008, 0.003)
    for i, b in enumerate(full):
        out.append(
            Bar(
                symbol="X", tf="1m", ts=float(i * 60),
                open=b.close, high=b.close, low=b.close, close=b.close,
                volume=1.0, closed=True,
            )
        )
    return _enrich(out, rng, vol_scale)


def _none_window(rng: random.Random) -> list[Bar]:
    """Pure random walk of length WINDOW. Ensures the model sees plenty of
    'no pattern here' so it doesn't default to a confident class."""
    base = rng.uniform(80.0, 30000.0)
    sigma = base * rng.uniform(0.001, 0.005)
    bars = _calm_walk(WINDOW, base, rng, sigma)
    return _enrich(bars, rng, sigma * rng.uniform(0.3, 1.0))


def build_dataset(per_class: int, none_count: int, seed: int = 0):
    """Return (X_full, X_early, y)."""
    rng = random.Random(seed)
    cls_idx = {n: i for i, n in enumerate(PATTERN_CLASSES)}
    X_full, X_early, y = [], [], []
    skipped = 0

    for pattern, factory in PATTERN_FACTORIES.items():
        idx = cls_idx[pattern]
        produced = 0
        attempts = 0
        while produced < per_class and attempts < per_class * 4:
            attempts += 1
            try:
                base = factory()
            except Exception:
                continue
            varied = _vary_pattern(base, rng)
            window_bars = _pad_into_window(varied, rng)
            full = bars_to_window(window_bars)
            early = early_window(window_bars, truncate_pct=rng.uniform(0.5, 0.85))
            if full is None or early is None:
                skipped += 1
                continue
            X_full.append(full)
            X_early.append(early)
            y.append(idx)
            produced += 1

    none_idx = cls_idx["none"]
    for _ in range(none_count):
        bars = _none_window(rng)
        full = bars_to_window(bars)
        early = early_window(bars, truncate_pct=rng.uniform(0.5, 0.85))
        if full is None or early is None:
            continue
        X_full.append(full)
        X_early.append(early)
        y.append(none_idx)

    print(f"built corpus: {len(y)} samples ({skipped} skipped)")
    return (
        np.stack(X_full).astype(np.float32),
        np.stack(X_early).astype(np.float32),
        np.array(y, dtype=np.int64),
    )


def write_csvs(out_dir: Path, per_class: int, seed: int) -> None:
    """Backwards-compat: emit per-pattern CSVs the old trainer can chew on."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.csv"):
        old.unlink()
    for pattern, factory in PATTERN_FACTORIES.items():
        long_run: list[Bar] = []
        ts = 0.0
        for _ in range(per_class):
            v = _vary_pattern(factory(), rng)
            window_bars = _pad_into_window(v, rng)
            for b in window_bars:
                b.ts = ts
                ts += 60.0
                long_run.append(b)
        path = out_dir / f"{pattern}.csv"
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts", "open", "high", "low", "close", "volume"])
            for b in long_run:
                w.writerow([b.ts, b.open, b.high, b.low, b.close, b.volume])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=400)
    ap.add_argument("--none-count", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-npz", default="../data/ml/corpus.npz")
    ap.add_argument("--out-csv", default=None,
                    help="Optional dir for per-pattern CSVs (backwards-compat).")
    args = ap.parse_args()

    X_full, X_early, y = build_dataset(args.per_class, args.none_count, args.seed)
    print(f"shape full={X_full.shape} early={X_early.shape} y={y.shape}")
    print("class counts:", dict(zip(PATTERN_CLASSES, np.bincount(y, minlength=len(PATTERN_CLASSES)).tolist())))

    out_path = Path(args.out_npz)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, X_full=X_full, X_early=X_early, y=y)
    print(f"wrote npz to {out_path}")

    if args.out_csv:
        write_csvs(Path(args.out_csv), args.per_class, args.seed)
        print(f"also wrote per-pattern CSVs to {args.out_csv}")


if __name__ == "__main__":
    main()
