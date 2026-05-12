"""End-to-end: synthetic ticks → engine → hub broadcast.

Asserts that feeding the bars from a textbook head-and-shoulders through the
engine produces at least one broadcast of type='detection' for the right
pattern.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.messages import Tick
from app.state import Engine
from app.ws_broadcast import Hub
import app.state as state_mod

from . import synth


class _CapturingWS:
    def __init__(self):
        self.sent: list[str] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


@pytest.mark.asyncio
async def test_engine_produces_head_and_shoulders_detection(monkeypatch):
    bars = synth.head_and_shoulders()
    hub = Hub()
    monkeypatch.setattr(state_mod, "hub", hub)
    engine = Engine()
    ws = _CapturingWS()
    await hub.subscribe(ws, bars[0].symbol, "1m")

    # Replay the synthetic bars as bar-close ticks.
    for b in bars:
        await engine.on_tick(
            Tick(symbol=b.symbol, ts=b.ts + 59.0, price=b.close, volume=b.volume),
            tf="1m",
        )
        # advance into the next bucket so the bar closes
        await engine.on_tick(
            Tick(symbol=b.symbol, ts=b.ts + 60.0, price=b.close, volume=0.0),
            tf="1m",
        )

    detections = [json.loads(m) for m in ws.sent if '"detection"' in m]
    patterns = {d["payload"]["pattern"] for d in detections}
    assert "head_and_shoulders" in patterns, patterns
