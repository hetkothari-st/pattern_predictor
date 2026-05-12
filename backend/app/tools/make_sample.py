"""Write a tick-style CSV from one of the synthetic pattern generators
so the replay tool has something to chew on out of the box.

Usage:
    python -m app.tools.make_sample --pattern head_and_shoulders --out ../data/sample.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

from tests import synth  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="head_and_shoulders")
    ap.add_argument("--out", default="../data/sample.csv")
    args = ap.parse_args()
    factory = getattr(synth, args.pattern, None)
    if factory is None:
        raise SystemExit(f"unknown pattern: {args.pattern}")
    bars = factory()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.write("ts,price,volume\n")
        for b in bars:
            f.write(f"{b.ts},{b.close},{b.volume}\n")
    print(f"wrote {len(bars)} ticks to {out}")


if __name__ == "__main__":
    main()
