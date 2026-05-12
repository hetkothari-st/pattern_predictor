"""Per-(symbol, tf) fan-out to connected frontend WebSockets."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

from .messages import WSOut

log = logging.getLogger(__name__)


class Hub:
    def __init__(self) -> None:
        self._subs: dict[tuple[str, str], set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, ws: WebSocket, symbol: str, tf: str) -> None:
        async with self._lock:
            self._subs[(symbol, tf)].add(ws)

    async def unsubscribe(self, ws: WebSocket, symbol: str, tf: str) -> None:
        async with self._lock:
            self._subs[(symbol, tf)].discard(ws)

    async def publish(self, symbol: str, tf: str, msg: WSOut) -> None:
        dead: list[WebSocket] = []
        data = msg.model_dump_json()
        for ws in list(self._subs.get((symbol, tf), set())):
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._subs[(symbol, tf)].discard(ws)


hub = Hub()
