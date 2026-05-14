"""Historical bar retrieval tests — pure-function, no engine."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.history import bars_in_range, day_to_range, period_to_range, trading_days


def _write(tmp_path, symbol, tf, rows):
    safe = "".join(c if c.isalnum() else "_" for c in symbol)
    p = tmp_path / f"{safe}_{tf}.csv"
    p.write_text(
        "ts,open,high,low,close,volume\n"
        + "\n".join(f"{ts},{c},{c},{c},{c},1" for ts, c in rows)
    )
    return p


def test_bars_in_range_filters(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ohlcv_dir", str(tmp_path))
    _write(tmp_path, "X", "1m", [(60, 100), (120, 101), (180, 102), (240, 103)])
    bars = bars_in_range("X", "1m", start_ts=120, end_ts=240)
    # Inclusive start, exclusive end
    assert [b.ts for b in bars] == [120, 180]


def test_bars_in_range_open_ended(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ohlcv_dir", str(tmp_path))
    _write(tmp_path, "X", "1m", [(60, 100), (120, 101), (180, 102)])
    assert len(bars_in_range("X", "1m")) == 3


def test_trading_days_returns_unique_dates(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ohlcv_dir", str(tmp_path))
    ist = ZoneInfo("Asia/Kolkata")
    # Two bars on 2026-05-14, one on 2026-05-15.
    t1 = datetime(2026, 5, 14, 10, 0, tzinfo=ist).timestamp()
    t2 = datetime(2026, 5, 14, 14, 0, tzinfo=ist).timestamp()
    t3 = datetime(2026, 5, 15, 11, 0, tzinfo=ist).timestamp()
    _write(tmp_path, "X", "1m", [(t1, 100), (t2, 101), (t3, 102)])
    days = trading_days("X", "1m", limit=10)
    assert days == ["2026-05-15", "2026-05-14"]


def test_day_to_range_ist():
    s, e = day_to_range("2026-05-14")
    ist = ZoneInfo("Asia/Kolkata")
    assert datetime.fromtimestamp(s, tz=ist).hour == 0
    assert datetime.fromtimestamp(e, tz=ist).day == 15


def test_period_to_range():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    s, e = period_to_range("7d", now=now)
    assert e - s == 7 * 86400


def test_bars_in_range_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ohlcv_dir", str(tmp_path))
    assert bars_in_range("DOESNOTEXIST", "1m") == []
