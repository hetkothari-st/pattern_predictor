"""OHLCV -> normalised feature window for the CNN."""
from __future__ import annotations

import numpy as np

from ..messages import Bar

WINDOW = 120  # bars per sample
CHANNELS = 5  # open, high, low, close, log-volume


def bars_to_window(bars: list[Bar], *, n: int = WINDOW) -> np.ndarray | None:
    """Return a (CHANNELS, n) float32 array, or None if not enough bars."""
    if len(bars) < n:
        return None
    sl = bars[-n:]
    close = np.array([b.close for b in sl], dtype=np.float32)
    mean = close.mean()
    std = max(close.std(), 1e-6)
    o = (np.array([b.open for b in sl], dtype=np.float32) - mean) / std
    h = (np.array([b.high for b in sl], dtype=np.float32) - mean) / std
    l_ = (np.array([b.low for b in sl], dtype=np.float32) - mean) / std
    c = (close - mean) / std
    v = np.log1p(np.array([b.volume for b in sl], dtype=np.float32))
    v = (v - v.mean()) / max(v.std(), 1e-6)
    return np.stack([o, h, l_, c, v], axis=0)


def early_window(bars: list[Bar], truncate_pct: float = 0.7, *, n: int = WINDOW) -> np.ndarray | None:
    """For early-warning training: keep only the first `truncate_pct` of a pattern window,
    pad the tail with the last seen close so the network learns "what comes next"."""
    if len(bars) < n:
        return None
    sl = bars[-n:]
    keep = int(n * truncate_pct)
    padded = list(sl[:keep])
    fill = padded[-1]
    while len(padded) < n:
        padded.append(fill)
    return bars_to_window(padded, n=n)
