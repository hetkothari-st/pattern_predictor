"""Demo tick generator. Runs only when PRICE_WS_URL is empty so the user can
see a moving chart without wiring a live feed.

Each known index gets a geometric random walk anchored to a realistic price.
Every ~250ms we push a tick for one symbol; the engine aggregates into bars
exactly the same way it would for live MT data.

Periodically (every ~3 minutes), one symbol is hijacked to replay a synthetic
pattern shape (head & shoulders, double top, triangle, etc) so the rule
detectors actually see textbook completions and the Playbook / Reference /
Critic panels populate. Without this, pure random walks rarely break the
neckline cleanly and detections stay stuck at "forming".
"""
from __future__ import annotations

import asyncio
import logging
import random
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable

from .messages import Tick

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


def _pattern_factories():
    from tests import synth  # type: ignore

    return [
        ("head_and_shoulders", synth.head_and_shoulders),
        ("inverse_head_and_shoulders", synth.inverse_head_and_shoulders),
        ("double_top", synth.double_top),
        ("double_bottom", synth.double_bottom),
        ("ascending_triangle", synth.ascending_triangle),
        ("descending_triangle", synth.descending_triangle),
        ("bull_flag", synth.bull_flag),
        ("bear_flag", synth.bear_flag),
        ("cup_with_handle", synth.cup_with_handle),
    ]


async def _inject_pattern(
    symbol: str, anchor: float, sink: TickSink, factory, tick_interval: float
) -> None:
    """Replay a synth pattern as a tick stream — one synth bar per real-world
    minute, ~6 ticks per bar walking through OHLC. The detectors run on
    bar-close, so this gives them clean textbook geometry to chew on."""
    bars = factory()
    centre = sum(b.close for b in bars) / len(bars)
    scale = anchor * 0.012  # how big the pattern looks vs anchor price
    log.info("Injecting %s into %s (%d bars)", factory.__name__, symbol, len(bars))
    for i, b in enumerate(bars):
        # Map synth close into real price space around anchor.
        target = anchor + (b.close - centre) * scale / max(1.0, abs(centre) * 0.1)
        # Six intra-bar ticks walking toward target.
        for j in range(6):
            await sink(
                Tick(
                    symbol=symbol,
                    ts=time.time(),
                    price=target + (random.random() - 0.5) * scale * 0.05,
                    volume=random.uniform(50, 500),
                )
            )
            await asyncio.sleep(tick_interval)


async def run_demo(sink: TickSink, *, interval_s: float = 0.25) -> None:
    """Pump ticks forever. One tick per interval, round-robin across symbols.
    Each tick walks the price with a small Gaussian step + tiny mean reversion
    so it doesn't drift off-screen.

    Every PATTERN_EVERY_S seconds, one symbol is briefly hijacked to play out
    a textbook pattern shape so the detectors emit a real `completed` event.
    """
    rng = random.Random(7)
    state: dict[str, float] = dict(ANCHORS)
    symbols = list(ANCHORS.keys())
    factories = _pattern_factories()
    log.info("Demo feed running for %s every %.0fms", symbols, interval_s * 1000)

    PATTERN_EVERY_S = 180.0
    last_pattern = time.monotonic()
    pattern_cursor = 0

    while True:
        for symbol in symbols:
            anchor = ANCHORS[symbol]
            current = state[symbol]
            sigma = anchor * VOL[symbol]
            step = rng.gauss(0, sigma)
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

        # Periodic synth-pattern injection.
        if time.monotonic() - last_pattern >= PATTERN_EVERY_S:
            symbol = symbols[pattern_cursor % len(symbols)]
            name, factory = factories[pattern_cursor % len(factories)]
            pattern_cursor += 1
            try:
                await _inject_pattern(
                    symbol,
                    state[symbol],
                    sink,
                    factory,
                    tick_interval=interval_s / 6,
                )
                # Re-anchor so the demo doesn't drift after the injection.
                state[symbol] = state[symbol]
            except Exception as exc:  # noqa: BLE001
                log.warning("pattern injection failed: %s", exc)
            last_pattern = time.monotonic()
