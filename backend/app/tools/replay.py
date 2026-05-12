"""Stream a historical CSV through the same engine the live WS uses, so the
full UI can be exercised offline.

Usage:
    python -m app.tools.replay --csv data/sample.csv --symbol BTCUSDT --tf 1m --speed 60

The CSV needs columns: ts (unix seconds), price, volume (optional).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from ..config import settings
from ..messages import Tick
from ..state import engine

log = logging.getLogger("replay")


async def run(csv_path: Path, symbol: str, tf: str, speed: float) -> None:
    import pandas as pd

    df = pd.read_csv(csv_path)
    if "ts" not in df.columns or "price" not in df.columns:
        raise SystemExit("CSV must have columns: ts, price [, volume]")
    last_ts: float | None = None
    for _, row in df.iterrows():
        ts = float(row["ts"])
        if last_ts is not None and speed > 0:
            await asyncio.sleep(max(0.0, (ts - last_ts) / speed))
        last_ts = ts
        tick = Tick(
            symbol=symbol,
            ts=ts,
            price=float(row["price"]),
            volume=float(row.get("volume", 0.0)),
        )
        await engine.on_tick(tick, tf=tf)
    log.info("replay finished")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--symbol", default=settings.default_symbol)
    ap.add_argument("--tf", default=settings.default_timeframe)
    ap.add_argument("--speed", type=float, default=60.0, help="x wall-clock; 0 = max speed")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(Path(args.csv), args.symbol, args.tf, args.speed))


if __name__ == "__main__":
    main()
