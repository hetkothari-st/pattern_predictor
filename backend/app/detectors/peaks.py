"""Peak/trough finder. Thin wrapper over scipy.signal.find_peaks.

Prominence is tuned to ATR so the detector behaves the same on a $30k BTC chart
and a $200 stock.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from .base import atr


def find_pivots(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    prom_atr: float = 0.6,
    distance: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (peak_indices, trough_indices). Empty arrays if data too short."""
    if len(close) < max(distance * 2 + 1, 5):
        return np.array([], dtype=int), np.array([], dtype=int)
    a = atr(high, low, close)
    if a <= 0:
        a = max(1e-9, np.std(close))
    prom = prom_atr * a
    peaks, _ = find_peaks(high, prominence=prom, distance=distance)
    troughs, _ = find_peaks(-low, prominence=prom, distance=distance)
    return peaks.astype(int), troughs.astype(int)
