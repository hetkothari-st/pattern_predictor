"""Rising wedge (bearish) and falling wedge (bullish)."""
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


class Wedge(PatternDetector):
    name = "wedge"

    def detect(self, bars: list[Bar]) -> list[Detection]:
        a = bars_to_arrays(bars)
        peaks, troughs = find_pivots(a["high"], a["low"], a["close"])
        if len(peaks) < 2 or len(troughs) < 2 or len(bars) < 20:
            return []
        peaks = peaks[-4:]
        troughs = troughs[-4:]
        m_top, b_top = _line(peaks.astype(float), a["high"][peaks])
        m_bot, b_bot = _line(troughs.astype(float), a["low"][troughs])
        scale = max(1e-9, np.std(a["close"][-50:]) / max(1, len(a["close"][-50:])))
        s_top = m_top / scale
        s_bot = m_bot / scale

        kind: str | None = None
        direction: str = "bearish"
        # Rising wedge: both slopes positive, lower steeper than upper.
        if s_top > 0.1 and s_bot > 0.1 and s_bot > s_top * 1.2:
            kind, direction = "rising_wedge", "bearish"
        # Falling wedge: both slopes negative, upper steeper (more negative) than lower.
        elif s_top < -0.1 and s_bot < -0.1 and s_top < s_bot * 1.2:
            kind, direction = "falling_wedge", "bullish"
        if kind is None:
            return []

        x_last = float(len(bars) - 1)
        top_at_last = m_top * x_last + b_top
        bot_at_last = m_bot * x_last + b_bot
        last_close = float(a["close"][-1])
        broken = (
            (direction == "bullish" and last_close > top_at_last)
            or (direction == "bearish" and last_close < bot_at_last)
        )
        status = "completed" if broken else "forming"
        confidence = 0.6 if status == "completed" else 0.4
        ts = a["ts"]
        idx = np.unique(np.concatenate([peaks, troughs]))
        anchors = [
            AnchorPoint(
                ts=float(ts[i]),
                price=float(a["high"][i] if i in peaks else a["low"][i]),
                label="upper" if i in peaks else "lower",
            )
            for i in idx
        ]
        return [
            Detection(
                id=_id(kind, [ts[idx[0]], ts[idx[-1]]]),
                pattern=kind,
                direction=direction,  # type: ignore[arg-type]
                status=status,
                confidence=confidence,
                start_ts=float(ts[idx[0]]),
                end_ts=float(ts[idx[-1]]),
                anchors=anchors,
            )
        ]
