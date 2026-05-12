"""Demo tick generator. Runs only when PRICE_WS_URL is empty so the user can
see a moving chart without wiring a live feed.

Each known index gets a geometric random walk anchored to a realistic price.
Every ~250ms we push a tick for one symbol; the engine aggregates into bars
exactly the same way it would for live MT data.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Awaitable, Callable

from .messages import Tick

log = logging.getLogger(__name__)

TickSink = Callable[[Tick], Awaitable[None]]

# Anchor prices roughly match recent NSE/BSE values so the chart axes look
# right out of the box.
ANCHORS: dict[str, float] = {
    "NIFTY50": 23500.0,
    "NIFTYBANK": 53600.0,
    "FINNIFTY": 23300.0,
    "SENSEX": 77400.0,
}
# Per-tick volatility (fraction of price). Larger for indices that actually
# move more in absolute points.
VOL: dict[str, float] = {
    "NIFTY50": 0.0006,
    "NIFTYBANK": 0.0009,
    "FINNIFTY": 0.0006,
    "SENSEX": 0.0007,
}


async def run_demo(sink: TickSink, *, interval_s: float = 0.25) -> None:
    """Pump ticks forever. One tick per interval, round-robin across symbols.
    Each tick walks the price with a small Gaussian step + tiny mean reversion
    so it doesn't drift off-screen.
    """
    rng = random.Random(7)
    state: dict[str, float] = dict(ANCHORS)
    symbols = list(ANCHORS.keys())
    log.info("Demo feed running for %s every %.0fms", symbols, interval_s * 1000)
    while True:
        for symbol in symbols:
            anchor = ANCHORS[symbol]
            current = state[symbol]
            sigma = anchor * VOL[symbol]
            step = rng.gauss(0, sigma)
            # Mean reversion: pull toward the anchor by 0.5% of the gap.
            current += step + (anchor - current) * 0.005
            state[symbol] = current
            await sink(
                Tick(
                    symbol=symbol,
                    ts=time.time(),
                    price=current,
                    volume=rng.uniform(50, 500),
                )
            )
            await asyncio.sleep(interval_s / max(1, len(symbols)))
