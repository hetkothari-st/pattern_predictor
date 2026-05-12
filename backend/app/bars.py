"""Tick -> OHLCV bar aggregation, per (symbol, timeframe), in-memory ring buffer."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .config import settings
from .messages import Bar, Tick

TF_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def floor_to_tf(ts: float, tf: str) -> float:
    step = TF_SECONDS[tf]
    return float(int(ts // step) * step)


@dataclass
class _Building:
    bar: Bar | None = None


@dataclass
class BarStream:
    symbol: str
    tf: str
    max_len: int = field(default_factory=lambda: settings.bar_history)
    closed: deque[Bar] = field(init=False)
    forming: _Building = field(default_factory=_Building, init=False)

    def __post_init__(self) -> None:
        self.closed = deque(maxlen=self.max_len)

    def ingest(self, tick: Tick) -> list[Bar]:
        """Apply a tick. Returns one or two bars to emit:
        - The updated forming bar (closed=False), and
        - The bar that just closed (closed=True), if a boundary was crossed.
        """
        bucket_ts = floor_to_tf(tick.ts, self.tf)
        emit: list[Bar] = []
        b = self.forming.bar
        if b is None or bucket_ts > b.ts:
            if b is not None:
                b.closed = True
                self.closed.append(b)
                emit.append(b)
            b = Bar(
                symbol=self.symbol,
                tf=self.tf,
                ts=bucket_ts,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.volume,
                closed=False,
            )
            self.forming.bar = b
        else:
            b.high = max(b.high, tick.price)
            b.low = min(b.low, tick.price)
            b.close = tick.price
            b.volume += tick.volume
        emit.append(b)
        return emit

    def snapshot(self) -> list[Bar]:
        out = list(self.closed)
        if self.forming.bar is not None:
            out.append(self.forming.bar)
        return out


class BarStore:
    """Map of (symbol, tf) -> BarStream."""

    def __init__(self) -> None:
        self._streams: dict[tuple[str, str], BarStream] = {}

    def get(self, symbol: str, tf: str) -> BarStream:
        key = (symbol, tf)
        if key not in self._streams:
            self._streams[key] = BarStream(symbol=symbol, tf=tf)
        return self._streams[key]


store = BarStore()
