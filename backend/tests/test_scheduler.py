"""Market-hours scheduler — pure-function tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.scheduler import IST, _is_trading_day, _next_market_open, is_market_open


def _ist(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=IST)


def test_weekend_is_not_trading_day():
    sat = date(2026, 5, 16)
    sun = date(2026, 5, 17)
    assert sat.weekday() == 5
    assert _is_trading_day(sat, set()) is False
    assert _is_trading_day(sun, set()) is False


def test_holiday_is_not_trading_day():
    holiday = date(2026, 1, 26)
    assert _is_trading_day(holiday, {holiday}) is False


def test_market_open_window():
    # 09:15 — open. 15:29 — open. 15:30 — closed. 09:14 — closed.
    assert is_market_open(_ist(2026, 5, 14, 9, 15), set()) is True
    assert is_market_open(_ist(2026, 5, 14, 15, 29), set()) is True
    assert is_market_open(_ist(2026, 5, 14, 15, 30), set()) is False
    assert is_market_open(_ist(2026, 5, 14, 9, 14), set()) is False


def test_market_closed_on_weekend():
    sat = _ist(2026, 5, 16, 11, 0)
    assert is_market_open(sat, set()) is False


def test_next_market_open_after_close_today():
    closed = _ist(2026, 5, 14, 16, 0)  # Thursday after close
    nxt = _next_market_open(closed, set())
    assert nxt.date() == date(2026, 5, 15)  # Friday
    assert nxt.time().hour == 9 and nxt.time().minute == 15


def test_next_market_open_skips_weekend():
    fri_close = _ist(2026, 5, 15, 16, 0)
    nxt = _next_market_open(fri_close, set())
    assert nxt.date() == date(2026, 5, 18)  # following Monday


def test_next_market_open_skips_holiday():
    # Wed 2026-08-12, holiday on Thu 2026-08-13. Next trading day = Fri.
    holidays = {date(2026, 8, 13)}
    wed_close = _ist(2026, 8, 12, 16, 0)
    nxt = _next_market_open(wed_close, holidays)
    assert nxt.date() == date(2026, 8, 14)


def test_pre_market_returns_today_open():
    early = _ist(2026, 5, 14, 7, 0)
    nxt = _next_market_open(early, set())
    assert nxt.date() == date(2026, 5, 14)
    assert nxt.time().hour == 9
