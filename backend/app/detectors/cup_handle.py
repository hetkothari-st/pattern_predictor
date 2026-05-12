"""Cup-with-handle (bullish continuation)."""
from __future__ import annotations

import hashlib

import numpy as np

from ..messages import AnchorPoint, Bar, Detection
from .base import PatternDetector, bars_to_arrays
from .peaks import find_pivots


def _id(prefix: str, ts_values: list[float]) -> str:
    key = prefix + "|" + ",".join(f"{t:.0f}" for t in ts_values)
    return hashlib.md5(key.encode()).hexdigest()[:12]


class CupHandle(PatternDetector):
    name = "cup_with_handle"

    def detect(self, bars: list[Bar]) -> list[Detection]:
        a = bars_to_arrays(bars)
        n = len(bars)
        if n < 30:
            return []
        peaks, troughs = find_pivots(a["high"], a["low"], a["close"])
        if len(peaks) < 2 or len(troughs) < 1:
            return []
        high = a["high"]
        low = a["low"]
        ts = a["ts"]
        # Look for a U-shape: two peaks at similar height with a deep trough between.
        for i in range(len(peaks) - 1):
            i_l = int(peaks[i])
            i_r = int(peaks[i + 1])
            if i_r - i_l < 15:
                continue
            p_l, p_r = high[i_l], high[i_r]
            if abs(p_l - p_r) / max(1e-9, p_l) > 0.04:
                continue
            mids = troughs[(troughs > i_l) & (troughs < i_r)]
            if len(mids) == 0:
                continue
            i_b = int(mids[np.argmin(low[mids])])
            depth = (p_l - low[i_b]) / max(1e-9, p_l)
            if not (0.10 <= depth <= 0.50):  # Bulkowski's cup depth band
                continue
            # Handle: short pullback after the right rim.
            handle_zone_end = min(n, i_r + 10)
            handle_low = float(low[i_r:handle_zone_end].min()) if handle_zone_end > i_r else float(low[i_r])
            handle_depth = (p_r - handle_low) / max(1e-9, p_r)
            if not (0.01 <= handle_depth <= 0.15):
                continue
            last_close = float(a["close"][-1])
            broken = last_close > max(p_l, p_r)
            status = "completed" if broken else "forming"
            confidence = 0.65 if status == "completed" else 0.4
            anchors = [
                AnchorPoint(ts=float(ts[i_l]), price=float(p_l), label="left rim"),
                AnchorPoint(ts=float(ts[i_b]), price=float(low[i_b]), label="cup bottom"),
                AnchorPoint(ts=float(ts[i_r]), price=float(p_r), label="right rim"),
                AnchorPoint(ts=float(ts[handle_zone_end - 1]), price=handle_low, label="handle low"),
            ]
            return [
                Detection(
                    id=_id("cup_handle", [ts[i_l], ts[i_r]]),
                    pattern="cup_with_handle",
                    direction="bullish",
                    status=status,
                    confidence=confidence,
                    start_ts=float(ts[i_l]),
                    end_ts=float(ts[handle_zone_end - 1]),
                    anchors=anchors,
                    notes=f"cup depth {depth:.0%}, handle {handle_depth:.0%}",
                )
            ]
        return []
