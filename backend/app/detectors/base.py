from __future__ import annotations

import numpy as np

from ..messages import Bar


class PatternDetector:
    """Subclasses override `name` and `detect(bars)`."""

    name: str = "unknown"

    def detect(self, bars: list[Bar]):  # -> list[Detection]
        raise NotImplementedError


def bars_to_arrays(bars: list[Bar]) -> dict[str, np.ndarray]:
    if not bars:
        empty = np.array([], dtype=float)
        return {k: empty for k in ("ts", "open", "high", "low", "close", "volume")}
    arr = {
        "ts": np.array([b.ts for b in bars], dtype=float),
        "open": np.array([b.open for b in bars], dtype=float),
        "high": np.array([b.high for b in bars], dtype=float),
        "low": np.array([b.low for b in bars], dtype=float),
        "close": np.array([b.close for b in bars], dtype=float),
        "volume": np.array([b.volume for b in bars], dtype=float),
    }
    return arr


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> float:
    """Simple ATR over the trailing `n` bars. Returns a scalar (last value)."""
    if len(close) < 2:
        return 0.0
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    n = min(n, len(tr))
    return float(tr[-n:].mean())
