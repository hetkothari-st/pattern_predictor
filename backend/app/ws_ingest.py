"""Subscriber to the user's price WebSocket. Normalises ticks via a pluggable adapter."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

import websockets

from .config import settings
from .messages import Tick

log = logging.getLogger(__name__)

TickSink = Callable[[Tick], Awaitable[None]]


def parse_generic(raw: dict) -> Tick | None:
    """Adapter for `{symbol, ts, price, volume}`."""
    try:
        return Tick(
            symbol=raw["symbol"],
            ts=float(raw["ts"]),
            price=float(raw["price"]),
            volume=float(raw.get("volume", 0.0)),
        )
    except (KeyError, ValueError, TypeError):
        return None


def parse_binance_trade(raw: dict) -> Tick | None:
    """Adapter for Binance `@trade` stream payloads."""
    data = raw.get("data", raw)
    try:
        return Tick(
            symbol=data["s"],
            ts=float(data["T"]) / 1000.0,
            price=float(data["p"]),
            volume=float(data["q"]),
        )
    except (KeyError, ValueError, TypeError):
        return None


ADAPTERS = {"generic": parse_generic, "binance": parse_binance_trade}


async def run_ingest(sink: TickSink, *, url: str | None = None, fmt: str | None = None) -> None:
    """Connect, reconnect on failure, forward parsed ticks to `sink`."""
    url = url or settings.price_ws_url
    fmt = fmt or settings.price_ws_format
    if not url:
        log.warning("PRICE_WS_URL not set; ingest disabled. Use the replay tool for offline runs.")
        return
    if fmt == "mt":
        from .mt_feed import run_mt_ingest

        await run_mt_ingest(sink, url=url)
        return
    parse = ADAPTERS.get(fmt, parse_generic)
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info("Connected to price WS: %s", url)
                backoff = 1.0
                async for raw_msg in ws:
                    try:
                        obj = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        continue
                    tick = parse(obj)
                    if tick is not None:
                        await sink(tick)
        except Exception as exc:  # noqa: BLE001 — we want to keep trying
            log.warning("Ingest error: %s — reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
