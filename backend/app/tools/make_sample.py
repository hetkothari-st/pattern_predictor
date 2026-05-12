"""Write a tick-style CSV from one of the synthetic pattern generators
so the replay tool has something to chew on out of the box.

Each synthetic bar is exploded into ~8 micro-ticks that walk inside the bar's
OHLC envelope, so the resulting candles render with real bodies and wicks
rather than flat dashes.

Usage:
    python -m app.tools.make_sample --pattern head_and_shoulders --out ../data/sample.csv
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

from tests import synth  # type: ignore

random.seed(42)


def _explode(bar, n_ticks: int = 8) -> list[tuple[float, float]]:
    """Return n (ts, price) ticks within a bar envelope. Open first, close last,
    high/low touched somewhere in between, intermediate prices sampled in
    [low, high]."""
    span = max(1.0, n_ticks - 1)
    ticks: list[tuple[float, float]] = [(bar.ts, bar.open)]
    interior = max(0, n_ticks - 4)
    for i in range(1, 1 + interior):
        ts = bar.ts + (i / span) * 60.0
        price = random.uniform(bar.low, bar.high)
        ticks.append((ts, price))
    # Make sure the high and low are actually visited.
    ticks.append((bar.ts + (1 + interior) / span * 60.0, bar.high))
    ticks.append((bar.ts + (2 + interior) / span * 60.0, bar.low))
    ticks.append((bar.ts + 60.0 - 0.001, bar.close))
    return ticks


def _enrich(bar, jitter: float = 0.4):
    """Give a flat synth bar a real OHLC range — the synth generator only
    sets open=close=mid; we widen high/low so candle bodies appear."""
    mid = bar.close
    body = jitter * 0.6
    wick = jitter
    direction = random.choice([1, -1])
    open_ = mid - direction * body * 0.4
    close_ = mid + direction * body * 0.6
    high = max(open_, close_) + wick
    low = min(open_, close_) - wick
    bar.open = open_
    bar.close = close_
    bar.high = high
    bar.low = low
    return bar


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="head_and_shoulders")
    ap.add_argument("--out", default="../data/sample.csv")
    args = ap.parse_args()
    factory = getattr(synth, args.pattern, None)
    if factory is None:
        raise SystemExit(f"unknown pattern: {args.pattern}")
    bars = [_enrich(b) for b in factory()]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_ticks = 0
    with out.open("w") as f:
        f.write("ts,price,volume\n")
        for b in bars:
            for ts, price in _explode(b):
                f.write(f"{ts},{price},{b.volume / 8:.4f}\n")
                n_ticks += 1
    print(f"wrote {n_ticks} ticks ({len(bars)} bars) to {out}")


if __name__ == "__main__":
    main()
