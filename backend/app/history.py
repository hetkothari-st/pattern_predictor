"""Historical bar retrieval over recorded OHLCV CSVs.

`/api/bars/range` returns bars in a (start_ts, end_ts) window, reading from
the recorder CSVs the engine appends to. `/api/days` lists which calendar
days (IST) have at least one bar — drives the date picker.
"""
from __future__ import annotations

import csv
import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from .config import settings
from .messages import Bar

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
DAY_START_IST = time(0, 0)


def _csv_path(symbol: str, tf: str) -> Path:
    base = Path(settings.ohlcv_dir)
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent / base
    safe = "".join(c if c.isalnum() else "_" for c in symbol)
    return base / f"{safe}_{tf}.csv"


def _iter_rows(symbol: str, tf: str) -> Iterable[Bar]:
    path = _csv_path(symbol, tf)
    if not path.exists():
        return
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                yield Bar(
                    symbol=symbol,
                    tf=tf,
                    ts=float(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0) or 0),
                    closed=True,
                )
            except (KeyError, ValueError, TypeError):
                continue


def bars_in_range(
    symbol: str,
    tf: str,
    start_ts: float | None = None,
    end_ts: float | None = None,
) -> list[Bar]:
    """Return bars whose `ts` falls in [start_ts, end_ts). Inclusive on
    start, exclusive on end. Either bound may be None for open-ended."""
    out: list[Bar] = []
    for b in _iter_rows(symbol, tf):
        if start_ts is not None and b.ts < start_ts:
            continue
        if end_ts is not None and b.ts >= end_ts:
            continue
        out.append(b)
    return out


def trading_days(symbol: str, tf: str, limit: int = 60) -> list[str]:
    """Return up to `limit` recent calendar days (YYYY-MM-DD, IST) for which
    we have at least one bar. Newest first."""
    days: set[str] = set()
    for b in _iter_rows(symbol, tf):
        dt = datetime.fromtimestamp(b.ts, tz=timezone.utc).astimezone(IST)
        days.add(dt.strftime("%Y-%m-%d"))
    return sorted(days, reverse=True)[:limit]


def day_to_range(day: str) -> tuple[float, float]:
    """Convert an IST calendar day (YYYY-MM-DD) to a (start_ts, end_ts)
    unix-second window. End is 00:00 IST of the next day."""
    d = date.fromisoformat(day)
    start = datetime.combine(d, DAY_START_IST, tzinfo=IST).timestamp()
    end = datetime.combine(d + timedelta(days=1), DAY_START_IST, tzinfo=IST).timestamp()
    return start, end


def period_to_range(period: str, now: datetime | None = None) -> tuple[float, float]:
    """Convert "1d" / "7d" / "30d" / "90d" to a (start_ts, end_ts) range
    ending at `now` (default: current time)."""
    if now is None:
        now = datetime.now(tz=IST)
    end_ts = now.timestamp()
    days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = days_map.get(period)
    if days is None:
        raise ValueError(f"unknown period {period!r}")
    start_ts = (now - timedelta(days=days)).timestamp()
    return start_ts, end_ts
