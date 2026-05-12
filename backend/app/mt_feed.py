"""MT Data Feed adapter (the funnel-op WS protocol).

Stateful WebSocket client: connects, sends Login, sends TokenRequest
subscriptions, heartbeats every 3s, and emits normalized Ticks back through
the engine's `sink` callable.

Indices stream `IndexData` packets (single price per packet).
NSEFO/BSEFO depth streams `DepthData` packets (5-level book) — we synthesize a
mid-price tick from the top-of-book bid/ask.

Subscriptions come from settings.mt_subscriptions as a JSON list of
{Tkn, Xchg, Symbol, FeedType}. We send one TokenRequest per FeedType so the
upstream doesn't merge streams.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable

import websockets

from .config import settings
from .messages import Tick

log = logging.getLogger(__name__)

TickSink = Callable[[Tick], Awaitable[None]]

# IndexData packets sometimes omit Tkn — fall back to symbol -> token.
INDEX_SYMBOL_TO_TOKEN = {
    "NIFTY50": "26000",
    "NIFTY 50": "26000",
    "NIFTYBANK": "26009",
    "BANKNIFTY": "26009",
    "SENSEX": "1",
}


def _load_subs() -> list[dict]:
    raw = settings.mt_subscriptions.strip()
    if not raw:
        return []
    try:
        subs = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("MT_SUBSCRIPTIONS not valid JSON: %s", exc)
        return []
    if not isinstance(subs, list):
        log.error("MT_SUBSCRIPTIONS must be a JSON list of {Tkn,Xchg,Symbol,FeedType}")
        return []
    return [s for s in subs if isinstance(s, dict) and "Tkn" in s and "Symbol" in s]


def _token_to_symbol(subs: list[dict]) -> dict[str, str]:
    return {str(s["Tkn"]): s["Symbol"] for s in subs}


def _credentials() -> tuple[str, str]:
    if settings.mt_login_id and settings.mt_password:
        return settings.mt_login_id, settings.mt_password
    # Anonymous handshake — funnel-op uses the same trick for market data.
    cred = f"anon_{int(time.time())}_{id(object())}"
    return cred, cred


def _ticks_from_packet(
    msg_type: str,
    packet: dict,
    token_symbol: dict[str, str],
) -> list[Tick]:
    token = packet.get("Tkn") or packet.get("Token")
    if not token and msg_type == "IndexData":
        sym = (packet.get("Symbol") or "").upper()
        token = INDEX_SYMBOL_TO_TOKEN.get(sym)
    if not token:
        return []
    token = str(token)
    symbol = token_symbol.get(token) or packet.get("Symbol") or token
    now = time.time()

    if msg_type == "IndexData":
        price = packet.get("Price") or packet.get("ltp") or packet.get("LTP")
        if price is None:
            return []
        try:
            return [Tick(symbol=symbol, ts=now, price=float(price), volume=0.0)]
        except (ValueError, TypeError):
            return []

    if msg_type in ("DepthData", "Depth"):
        depths = packet.get("depths") or packet.get("Depths") or []
        if not depths:
            return []
        top = depths[0]
        bp = top.get("BP")
        sp = top.get("SP")
        if bp is None and sp is None:
            return []
        bid = float(bp) if bp is not None else float(sp)
        ask = float(sp) if sp is not None else float(bp)
        if bid <= 0 and ask <= 0:
            return []
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else (bid or ask)
        bq = float(top.get("BQ", 0) or 0)
        sq = float(top.get("SQ", 0) or 0)
        return [Tick(symbol=symbol, ts=now, price=mid, volume=bq + sq)]

    return []


async def _subscribe(ws: websockets.WebSocketClientProtocol, subs: list[dict]) -> None:
    by_feed: dict[int, list[dict]] = {}
    for s in subs:
        ft = int(s.get("FeedType", 1))
        by_feed.setdefault(ft, []).append(
            {"Tkn": str(s["Tkn"]), "Xchg": s.get("Xchg", "NSE"), "Symbol": s["Symbol"]}
        )
    for ft, quotes in by_feed.items():
        payload = {
            "Type": "TokenRequest",
            "Data": {"SubType": True, "FeedType": ft, "quotes": quotes},
        }
        await ws.send(json.dumps(payload))
        log.info("MT subscribed FeedType=%d tokens=%d", ft, len(quotes))


async def _heartbeat_loop(ws: websockets.WebSocketClientProtocol) -> None:
    try:
        while True:
            await asyncio.sleep(3.0)
            await ws.send(
                json.dumps(
                    {"Type": "Info", "Data": {"InfoType": "HB", "InfoMsg": "Heartbeat"}}
                )
            )
    except (asyncio.CancelledError, websockets.ConnectionClosed):
        return


async def run_mt_ingest(sink: TickSink, *, url: str | None = None) -> None:
    url = url or settings.price_ws_url
    if not url:
        log.warning("PRICE_WS_URL not set; MT ingest disabled.")
        return
    subs = _load_subs()
    if not subs:
        log.warning("MT_SUBSCRIPTIONS empty; MT ingest will receive no data.")
    token_symbol = _token_to_symbol(subs)
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info("MT WS connected: %s", url)
                backoff = 1.0
                login_id, password = _credentials()
                await ws.send(
                    json.dumps(
                        {
                            "Type": "Login",
                            "Data": {"LoginId": login_id, "Password": password},
                        }
                    )
                )
                activated = False
                hb_task: asyncio.Task | None = None
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    msg_type = msg.get("Type")
                    data = msg.get("Data")
                    if not activated:
                        if msg_type == "Login" and isinstance(data, dict) and data.get("Error"):
                            log.error("MT login failed: %s", data["Error"])
                            break
                        activated = True
                        await _subscribe(ws, subs)
                        hb_task = asyncio.create_task(_heartbeat_loop(ws), name="mt-hb")
                        if msg_type == "Login":
                            continue
                    if msg_type in ("IndexData", "DepthData", "Depth") and data is not None:
                        packets = data if isinstance(data, list) else [data]
                        for packet in packets:
                            for tick in _ticks_from_packet(msg_type, packet, token_symbol):
                                await sink(tick)
                if hb_task:
                    hb_task.cancel()
        except Exception as exc:  # noqa: BLE001 — keep retrying on any failure
            log.warning("MT ingest error: %s — reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
