"""Head-and-shoulders + inverse head-and-shoulders."""
from __future__ import annotations

import hashlib

import numpy as np

from ..messages import AnchorPoint, Bar, Detection
from .base import PatternDetector, bars_to_arrays
from .peaks import find_pivots


def _id(prefix: str, ts_values: list[float]) -> str:
    key = prefix + "|" + ",".join(f"{t:.0f}" for t in ts_values)
    return hashlib.md5(key.encode()).hexdigest()[:12]


class HeadAndShoulders(PatternDetector):
    name = "head_and_shoulders"

    def detect(self, bars: list[Bar]) -> list[Detection]:
        a = bars_to_arrays(bars)
        peaks, troughs = find_pivots(a["high"], a["low"], a["close"])
        out: list[Detection] = []
        out += self._scan(bars, a, peaks, troughs, bullish=False)
        out += self._scan(bars, a, troughs, peaks, bullish=True)
        return out

    def _scan(
        self,
        bars: list[Bar],
        a,
        majors: np.ndarray,
        minors: np.ndarray,
        *,
        bullish: bool,
    ) -> list[Detection]:
        if len(majors) < 3 or len(minors) < 2:
            return []
        high = a["high"]
        low = a["low"]
        ts = a["ts"]
        results: list[Detection] = []
        # For each window of three consecutive majors, test the H&S geometry.
        for i in range(len(majors) - 2):
            i_ls, i_h, i_rs = int(majors[i]), int(majors[i + 1]), int(majors[i + 2])
            if bullish:
                p_ls, p_h, p_rs = low[i_ls], low[i_h], low[i_rs]
                head_ok = p_h < p_ls and p_h < p_rs
            else:
                p_ls, p_h, p_rs = high[i_ls], high[i_h], high[i_rs]
                head_ok = p_h > p_ls and p_h > p_rs
            if not head_ok:
                continue
            shoulder_diff = abs(p_ls - p_rs) / max(1e-9, abs(p_h))
            if shoulder_diff > 0.06:  # shoulders within ~6%
                continue
            # Find the two intervening pivots of opposite kind (the neckline points).
            n1_candidates = minors[(minors > i_ls) & (minors < i_h)]
            n2_candidates = minors[(minors > i_h) & (minors < i_rs)]
            if len(n1_candidates) == 0 or len(n2_candidates) == 0:
                continue
            i_n1 = int(n1_candidates[-1])
            i_n2 = int(n2_candidates[0])
            if bullish:
                n1, n2 = high[i_n1], high[i_n2]
            else:
                n1, n2 = low[i_n1], low[i_n2]
            # Neckline roughly horizontal (small slope).
            if abs(n1 - n2) / max(1e-9, abs(p_h)) > 0.05:
                continue
            neckline = (n1 + n2) / 2.0
            last_close = a["close"][-1]
            # Status: completed iff close has broken neckline beyond the right shoulder.
            broken = (
                (not bullish and last_close < neckline and i_rs < len(bars) - 1)
                or (bullish and last_close > neckline and i_rs < len(bars) - 1)
            )
            status = "completed" if broken else "forming"
            confidence = 0.7 if status == "completed" else 0.45
            anchors = [
                AnchorPoint(ts=float(ts[i_ls]), price=float(p_ls), label="left shoulder"),
                AnchorPoint(ts=float(ts[i_n1]), price=float(n1), label="neckline pt 1"),
                AnchorPoint(ts=float(ts[i_h]), price=float(p_h), label="head"),
                AnchorPoint(ts=float(ts[i_n2]), price=float(n2), label="neckline pt 2"),
                AnchorPoint(ts=float(ts[i_rs]), price=float(p_rs), label="right shoulder"),
            ]
            results.append(
                Detection(
                    id=_id(
                        f"hs_{'inv' if bullish else 'reg'}",
                        [ts[i_ls], ts[i_h], ts[i_rs]],
                    ),
                    pattern="inverse_head_and_shoulders" if bullish else "head_and_shoulders",
                    direction="bullish" if bullish else "bearish",
                    status=status,
                    confidence=confidence,
                    start_ts=float(ts[i_ls]),
                    end_ts=float(ts[i_rs]),
                    anchors=anchors,
                    notes=f"neckline @ {neckline:.4f}",
                )
            )
        return results
