"""Double top (bearish) and double bottom (bullish)."""
from __future__ import annotations

import hashlib

import numpy as np

from ..messages import AnchorPoint, Bar, Detection
from .base import PatternDetector, bars_to_arrays
from .peaks import find_pivots


def _id(prefix: str, ts_values: list[float]) -> str:
    key = prefix + "|" + ",".join(f"{t:.0f}" for t in ts_values)
    return hashlib.md5(key.encode()).hexdigest()[:12]


class DoubleTopBottom(PatternDetector):
    name = "double_top_bottom"

    def detect(self, bars: list[Bar]) -> list[Detection]:
        a = bars_to_arrays(bars)
        peaks, troughs = find_pivots(a["high"], a["low"], a["close"])
        out: list[Detection] = []
        out += self._scan(bars, a, peaks, troughs, bullish=False)
        out += self._scan(bars, a, troughs, peaks, bullish=True)
        return out

    def _scan(self, bars, a, majors, minors, *, bullish: bool) -> list[Detection]:
        if len(majors) < 2 or len(minors) < 1:
            return []
        high = a["high"]
        low = a["low"]
        ts = a["ts"]
        results: list[Detection] = []
        for i in range(len(majors) - 1):
            i1, i2 = int(majors[i]), int(majors[i + 1])
            if i2 - i1 < 5:
                continue
            if bullish:
                p1, p2 = low[i1], low[i2]
            else:
                p1, p2 = high[i1], high[i2]
            if abs(p1 - p2) / max(1e-9, abs(p1)) > 0.03:
                continue
            mid_candidates = minors[(minors > i1) & (minors < i2)]
            if len(mid_candidates) == 0:
                continue
            i_mid = int(mid_candidates[np.argmax(high[mid_candidates] if bullish else -low[mid_candidates])])
            if bullish:
                mid_price = high[i_mid]
                trough_depth = (mid_price - max(p1, p2)) / max(1e-9, mid_price)
            else:
                mid_price = low[i_mid]
                trough_depth = (min(p1, p2) - mid_price) / max(1e-9, min(p1, p2))
            if trough_depth < 0.02:
                continue
            last_close = a["close"][-1]
            broken = (
                (not bullish and last_close < mid_price)
                or (bullish and last_close > mid_price)
            )
            status = "completed" if broken else "forming"
            confidence = 0.65 if status == "completed" else 0.4
            anchors = [
                AnchorPoint(ts=float(ts[i1]), price=float(p1), label="first"),
                AnchorPoint(ts=float(ts[i_mid]), price=float(mid_price), label="confirmation level"),
                AnchorPoint(ts=float(ts[i2]), price=float(p2), label="second"),
            ]
            pattern = "double_bottom" if bullish else "double_top"
            results.append(
                Detection(
                    id=_id(pattern, [ts[i1], ts[i2]]),
                    pattern=pattern,
                    direction="bullish" if bullish else "bearish",
                    status=status,
                    confidence=confidence,
                    start_ts=float(ts[i1]),
                    end_ts=float(ts[i2]),
                    anchors=anchors,
                    notes=f"confirmation @ {mid_price:.4f}",
                )
            )
        return results
