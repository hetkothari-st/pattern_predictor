"""Synthetic OHLCV generators that produce textbook chart-pattern shapes.

Bars are spaced 1 minute apart. Volatility is deliberately low so the geometry
dominates over noise — the rule detectors should fire on these.
"""
from __future__ import annotations

import math
import random
from collections.abc import Iterable

from app.messages import Bar

random.seed(0)
TF_S = 60


def _bar(symbol: str, ts: float, price: float, *, noise: float = 0.05) -> Bar:
    o = price
    h = price + abs(noise)
    l = price - abs(noise)  # noqa: E741
    return Bar(symbol=symbol, tf="1m", ts=ts, open=o, high=h, low=l, close=price, volume=1.0, closed=True)


def from_prices(prices: Iterable[float], *, symbol: str = "TEST", t0: float = 0.0, noise: float = 0.05) -> list[Bar]:
    out: list[Bar] = []
    for i, p in enumerate(prices):
        out.append(_bar(symbol, t0 + i * TF_S, p, noise=noise))
    return out


def head_and_shoulders(*, neckline: float = 100.0, height: float = 10.0) -> list[Bar]:
    # 100 bars: rise -> left shoulder -> dip -> head -> dip -> right shoulder -> break below neckline.
    base = []
    base += _ramp(95, neckline + height * 0.6, 12)          # rise to LS
    base += _ramp(base[-1], neckline + 1, 8)                # dip toward neckline
    base += _ramp(base[-1], neckline + height, 12)          # rise to head
    base += _ramp(base[-1], neckline + 1, 12)               # dip
    base += _ramp(base[-1], neckline + height * 0.6, 10)    # right shoulder
    base += _ramp(base[-1], neckline - 5, 14)               # break below neckline
    return from_prices(base, noise=0.1)


def inverse_head_and_shoulders(*, neckline: float = 100.0, depth: float = 10.0) -> list[Bar]:
    base = []
    base += _ramp(105, neckline - depth * 0.6, 12)
    base += _ramp(base[-1], neckline - 1, 8)
    base += _ramp(base[-1], neckline - depth, 12)
    base += _ramp(base[-1], neckline - 1, 12)
    base += _ramp(base[-1], neckline - depth * 0.6, 10)
    base += _ramp(base[-1], neckline + 5, 14)
    return from_prices(base, noise=0.1)


def double_top(*, level: float = 100.0, dip: float = 6.0) -> list[Bar]:
    base = []
    base += _ramp(90, level, 12)
    base += _ramp(level, level - dip, 10)
    base += _ramp(level - dip, level, 10)
    base += _ramp(level, level - dip - 4, 16)
    return from_prices(base, noise=0.1)


def double_bottom(*, level: float = 100.0, bump: float = 6.0) -> list[Bar]:
    base = []
    base += _ramp(110, level, 12)
    base += _ramp(level, level + bump, 10)
    base += _ramp(level + bump, level, 10)
    base += _ramp(level, level + bump + 4, 16)
    return from_prices(base, noise=0.1)


def ascending_triangle(*, level: float = 100.0, low_start: float = 90.0) -> list[Bar]:
    base = []
    n = 60
    for i in range(n):
        # Top oscillates near `level`; bottom rises linearly.
        top = level
        bot = low_start + (level - low_start - 2) * (i / n)
        # Alternate touching top/bottom
        base.append(top if i % 4 == 0 else (bot if i % 4 == 2 else (top + bot) / 2))
    # Breakout above level
    base += _ramp(level, level + 6, 12)
    return from_prices(base, noise=0.1)


def descending_triangle(*, level: float = 100.0, high_start: float = 110.0) -> list[Bar]:
    base = []
    n = 60
    for i in range(n):
        bot = level
        top = high_start - (high_start - level - 2) * (i / n)
        base.append(bot if i % 4 == 0 else (top if i % 4 == 2 else (top + bot) / 2))
    base += _ramp(level, level - 6, 12)
    return from_prices(base, noise=0.1)


def symmetric_triangle() -> list[Bar]:
    base = []
    n = 60
    top0, bot0 = 110.0, 90.0
    for i in range(n):
        top = top0 - (top0 - 100.0 - 2) * (i / n)
        bot = bot0 + (100.0 - bot0 - 2) * (i / n)
        base.append(top if i % 4 == 0 else (bot if i % 4 == 2 else (top + bot) / 2))
    base += _ramp(base[-1], base[-1] + 6, 10)
    return from_prices(base, noise=0.1)


def rising_wedge() -> list[Bar]:
    # Both bounds rise but lower rises faster -> converging upward.
    base = []
    n = 60
    for i in range(n):
        top = 100 + 0.05 * i
        bot = 95 + 0.12 * i
        base.append(top if i % 4 == 0 else (bot if i % 4 == 2 else (top + bot) / 2))
    base += _ramp(base[-1], base[-1] - 4, 10)
    return from_prices(base, noise=0.1)


def falling_wedge() -> list[Bar]:
    base = []
    n = 60
    for i in range(n):
        top = 110 - 0.12 * i
        bot = 100 - 0.05 * i
        base.append(top if i % 4 == 0 else (bot if i % 4 == 2 else (top + bot) / 2))
    base += _ramp(base[-1], base[-1] + 4, 10)
    return from_prices(base, noise=0.1)


def bull_flag() -> list[Bar]:
    base = []
    base += _ramp(90, 110, 10)              # pole
    # Channel sloping slightly down; last bar must close above the upper line
    # so the detector flags it as "completed" on the trailing window.
    for i in range(11):
        base.append(110 - 0.4 * i + (1 if i % 2 == 0 else -1))
    base.append(base[-1] + 4)               # breakout on the final bar
    return from_prices(base, noise=0.1)


def cup_with_handle() -> list[Bar]:
    base = []
    # Left rim
    base += _ramp(90, 100, 8)
    # Cup down to ~85 (15% depth) and back.
    n = 24
    for i in range(n):
        theta = math.pi * (i / (n - 1))
        base.append(100 - 15 * math.sin(theta))
    # Right rim
    base += _ramp(base[-1], 100, 4)
    # Handle: ~5% pullback
    base += _ramp(100, 95, 4)
    base += _ramp(95, 100, 4)
    # Breakout
    base += _ramp(100, 106, 6)
    return from_prices(base, noise=0.1)


def _ramp(start: float, end: float, n: int) -> list[float]:
    if n <= 0:
        return []
    return [start + (end - start) * (i / max(1, n - 1)) for i in range(n)]
