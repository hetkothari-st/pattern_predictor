"""Bullish/bearish flag (channel after a strong move) and pennant (mini-triangle after a strong move)."""
from __future__ import annotations

import hashlib

import numpy as np

from ..messages import AnchorPoint, Bar, Detection
from .base import PatternDetector, bars_to_arrays
from .peaks import find_pivots


def _id(prefix: str, ts_values: list[float]) -> str:
    key = prefix + "|" + ",".join(f"{t:.0f}" for t in ts_values)
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _line(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if len(x) < 2:
        return 0.0, float(y[0]) if len(y) else 0.0
    m, b = np.polyfit(x, y, 1)
    return float(m), float(b)


class FlagPennant(PatternDetector):
    name = "flag_pennant"
    POLE_BARS = 10
    CONS_BARS = 12
    MIN_POLE_MOVE = 0.10  # require 10%+ pole — kills random ramps
    PARALLEL_TOL = 0.05
    SLOPE_TRIGGER = 0.15

    def detect(self, bars: list[Bar]) -> list[Detection]:
        a = bars_to_arrays(bars)
        n = len(bars)
        if n < self.POLE_BARS + self.CONS_BARS:
            return []
        close = a["close"]
        # Identify a strong "pole" leading into the most recent consolidation.
        pole_start = n - self.POLE_BARS - self.CONS_BARS
        pole_end = n - self.CONS_BARS
        pole_move = (close[pole_end - 1] - close[pole_start]) / max(1e-9, abs(close[pole_start]))
        if abs(pole_move) < self.MIN_POLE_MOVE:
            return []
        # Pole must dominate the consolidation: consolidation range must be
        # smaller than half the pole range, otherwise the "pole" is just noise.
        pole_range = abs(close[pole_end - 1] - close[pole_start])
        cons_range = float(np.max(a["high"][pole_end:]) - np.min(a["low"][pole_end:]))
        if cons_range > 0.5 * pole_range:
            return []
        direction = "bullish" if pole_move > 0 else "bearish"
        cons_lo = a["low"][pole_end:]
        cons_hi = a["high"][pole_end:]
        cons_x = np.arange(len(cons_lo), dtype=float)
        m_top, b_top = _line(cons_x, cons_hi)
        m_bot, b_bot = _line(cons_x, cons_lo)
        scale = max(1e-9, np.std(close[-50:]) / max(1, 50))
        s_top, s_bot = m_top / scale, m_bot / scale

        # Flag: parallel channel sloping against the pole.
        is_flag = abs(s_top - s_bot) < self.PARALLEL_TOL and (
            (direction == "bullish" and s_top < -self.SLOPE_TRIGGER)
            or (direction == "bearish" and s_top > self.SLOPE_TRIGGER)
        )
        # Pennant: converging triangle in the consolidation.
        is_pennant = (s_top < -self.SLOPE_TRIGGER and s_bot > self.SLOPE_TRIGGER)
        if not is_flag and not is_pennant:
            return []
        kind = ("bull_" if direction == "bullish" else "bear_") + ("flag" if is_flag else "pennant")

        x_last = float(len(cons_x) - 1)
        top_at_last = m_top * x_last + b_top
        bot_at_last = m_bot * x_last + b_bot
        last_close = float(close[-1])
        broken = (
            (direction == "bullish" and last_close > top_at_last)
            or (direction == "bearish" and last_close < bot_at_last)
        )
        status = "completed" if broken else "forming"
        confidence = 0.6 if status == "completed" else 0.4
        ts = a["ts"]
        anchors = [
            AnchorPoint(ts=float(ts[pole_start]), price=float(close[pole_start]), label="pole start"),
            AnchorPoint(ts=float(ts[pole_end - 1]), price=float(close[pole_end - 1]), label="pole end"),
            AnchorPoint(ts=float(ts[-1]), price=last_close, label="current"),
        ]
        # Stable id keyed only on the pole start: a sliding window must not
        # spawn a fresh detection every bar — it should update the same one.
        return [
            Detection(
                id=_id(kind, [ts[pole_start]]),
                pattern=kind,
                direction=direction,  # type: ignore[arg-type]
                status=status,
                confidence=confidence,
                start_ts=float(ts[pole_start]),
                end_ts=float(ts[-1]),
                anchors=anchors,
            )
        ]
