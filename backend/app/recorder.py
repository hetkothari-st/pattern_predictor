"""Append closed bars to per-(symbol, tf) CSV files and read them back.

Wired from `Engine.on_tick` so every bar that crosses its boundary lands on
disk. Files become the training corpus consumed by `app.ml.train` and the
bootstrap source so a fresh chart shows everything since market open instead
of starting empty.

Header is written once on file creation: `ts,open,high,low,close,volume`.
"""
from __future__ import annotations

import csv
import logging
import threading
from pathlib import Path

from .config import settings
from .messages import Bar

log = logging.getLogger(__name__)

_lock = threading.Lock()
_seen_files: set[Path] = set()


def _path_for(symbol: str, tf: str) -> Path:
    base = Path(settings.ohlcv_dir)
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent / base
    base.mkdir(parents=True, exist_ok=True)
    safe_symbol = "".join(c if c.isalnum() else "_" for c in symbol)
    return base / f"{safe_symbol}_{tf}.csv"


def load_recorded(symbol: str, tf: str) -> list[Bar]:
    """Return previously recorded bars for this stream, or [] if none."""
    path = _path_for(symbol, tf)
    if not path.exists():
        return []
    bars: list[Bar] = []
    try:
        with path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    bars.append(
                        Bar(
                            symbol=symbol,
                            tf=tf,
                            ts=float(row["ts"]),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=float(row.get("volume", 0.0) or 0.0),
                            closed=True,
                        )
                    )
                except (KeyError, ValueError, TypeError):
                    continue
    except OSError as exc:
        log.warning("could not read %s: %s", path, exc)
    return bars


def record_bar(bar: Bar) -> None:
    if not settings.record_ohlcv or not bar.closed:
        return
    path = _path_for(bar.symbol, bar.tf)
    with _lock:
        new_file = path not in _seen_files and not path.exists()
        _seen_files.add(path)
        try:
            with path.open("a", newline="") as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow(["ts", "open", "high", "low", "close", "volume"])
                writer.writerow([bar.ts, bar.open, bar.high, bar.low, bar.close, bar.volume])
        except OSError as exc:
            log.warning("recorder failed for %s: %s", path, exc)
