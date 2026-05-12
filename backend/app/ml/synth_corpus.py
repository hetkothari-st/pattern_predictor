"""Generate a labelled training corpus straight from `tests/synth.py`.

Each pattern factory produces one canonical bar sequence; we wrap that with
randomised price level, noise, time-shifting, and length variations to make
N samples per class. Add a `none` class via random walks. Output: writes
synthetic OHLCV CSVs into `data/ohlcv/_synth/` so `app.ml.train` picks them
up unchanged.

Usage:
    python -m app.ml.synth_corpus --per-class 200 --out ../data/ohlcv/_synth
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path
from typing import Callable

import sys

# Allow `from tests import synth` to work when run as a module.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import synth  # type: ignore  # noqa: E402

from ..messages import Bar  # noqa: E402

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
    "cup_with_handle": synth.cup_with_handle,
}


def _enrich(bar: Bar, jitter: float, direction: int) -> Bar:
    """Give a flat synth bar a real OHLC range so candles + ATR work."""
    mid = bar.close
    body = jitter * 0.6
    wick = jitter
    open_ = mid - direction * body * 0.4
    close_ = mid + direction * body * 0.6
    bar.open = open_
    bar.close = close_
    bar.high = max(open_, close_) + wick * random.uniform(0.5, 1.4)
    bar.low = min(open_, close_) - wick * random.uniform(0.5, 1.4)
    bar.volume = random.uniform(50, 500)
    return bar


def _vary(bars: list[Bar], rng: random.Random) -> list[Bar]:
    """Apply a randomised transform: shift price level, scale, add noise,
    randomise candle direction. Preserves shape so detectors still fire."""
    base_level = rng.uniform(50.0, 30000.0)
    scale = rng.uniform(0.6, 1.6)
    noise = rng.uniform(0.05, 0.25) * scale
    closes = [b.close for b in bars]
    centre = sum(closes) / len(closes)
    out: list[Bar] = []
    for i, b in enumerate(bars):
        new_close = base_level + (b.close - centre) * scale + rng.gauss(0, noise * 0.6)
        nb = Bar(
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
        direction = 1 if rng.random() < 0.5 else -1
        out.append(_enrich(nb, jitter=noise, direction=direction))
    return out


def random_walk(n: int, rng: random.Random) -> list[Bar]:
    base = rng.uniform(50.0, 30000.0)
    sigma = base * 0.005
    bars: list[Bar] = []
    price = base
    for i in range(n):
        price += rng.gauss(0, sigma) + (base - price) * 0.002
        bar = Bar(
            symbol="none",
            tf="1m",
            ts=float(i * 60),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=rng.uniform(50, 500),
            closed=True,
        )
        bars.append(_enrich(bar, jitter=sigma * 0.6, direction=1 if rng.random() < 0.5 else -1))
    return bars


def write_csv(out: Path, bars: list[Bar]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow([b.ts, b.open, b.high, b.low, b.close, b.volume])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=200)
    ap.add_argument("--noise-len", type=int, default=160, help="bar count per `none` walk")
    ap.add_argument("--out", default="../data/ohlcv/_synth")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(args.out)
    if out_dir.exists():
        for old in out_dir.glob("*.csv"):
            old.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    n_files = 0
    for pattern, factory in PATTERN_FACTORIES.items():
        # Each file becomes one long sequence stitched from N variations of the
        # canonical pattern, padded with random walk between, so the trainer's
        # auto_label sees the pattern many times per file.
        long_run: list[Bar] = []
        ts = 0.0
        for _ in range(args.per_class):
            v = _vary(factory(), rng)
            for b in v:
                b.ts = ts
                ts += 60.0
                long_run.append(b)
            # Cool-down random walk so detectors don't blur consecutive instances.
            walk = random_walk(60, rng)
            for b in walk:
                b.ts = ts
                ts += 60.0
                long_run.append(b)
        write_csv(out_dir / f"{pattern}.csv", long_run)
        n_files += 1

    # Pure-noise files (so the model learns "none" from realistic random walks).
    noise = random_walk(args.per_class * 200, rng)
    write_csv(out_dir / "noise.csv", noise)
    n_files += 1

    print(f"wrote {n_files} CSVs to {out_dir}")


if __name__ == "__main__":
    main()
