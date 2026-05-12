"""Replay a historical CSV by POSTing ticks to the running backend.

Use this for offline end-to-end testing: start the backend (`uvicorn app.main:app
--reload`), open the frontend, then run this tool against a CSV. Ticks land in
the same engine instance the WebSocket reads from, so the chart updates live.

Usage:
    python -m app.tools.replay --csv data/sample.csv --symbol BTCUSDT --tf 1m --speed 60
    python -m app.tools.replay --csv data/sample.csv --symbol TEST --speed 0  # full speed

The CSV needs columns: ts (unix seconds), price, volume (optional).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import httpx

from ..config import settings

log = logging.getLogger("replay")


async def run(csv_path: Path, symbol: str, tf: str, speed: float, base_url: str) -> None:
    import pandas as pd

    df = pd.read_csv(csv_path)
    if "ts" not in df.columns or "price" not in df.columns:
        raise SystemExit("CSV must have columns: ts, price [, volume]")
    url = f"{base_url.rstrip('/')}/api/tick"
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Confirm the backend is up before we start so the failure mode is obvious.
        try:
            r = await client.get(f"{base_url.rstrip('/')}/health")
            r.raise_for_status()
        except Exception as exc:
            raise SystemExit(
                f"Backend not reachable at {base_url}. Start it first with: "
                f"uvicorn app.main:app --reload\n({exc})"
            )
        last_ts: float | None = None
        for i, row in df.iterrows():
            ts = float(row["ts"])
            if last_ts is not None and speed > 0:
                await asyncio.sleep(max(0.0, (ts - last_ts) / speed))
            last_ts = ts
            payload = {
                "symbol": symbol,
                "ts": ts,
                "price": float(row["price"]),
                "volume": float(row.get("volume", 0.0)),
            }
            try:
                resp = await client.post(url, params={"tf": tf}, json=payload)
                resp.raise_for_status()
            except Exception as exc:
                log.warning("tick %d failed: %s", i, exc)
        log.info("replay finished (%d ticks)", len(df))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--symbol", default=settings.default_symbol)
    ap.add_argument("--tf", default=settings.default_timeframe)
    ap.add_argument("--speed", type=float, default=60.0, help="x wall-clock; 0 = max speed")
    ap.add_argument("--url", default="http://localhost:8000", help="Backend base URL")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(run(Path(args.csv), args.symbol, args.tf, args.speed, args.url))


if __name__ == "__main__":
    main()
