"""NSE market-hours scheduler.

Runs an `ingest` task only between 09:15 and 15:30 IST on trading days,
sleeps the rest of the time, and self-restarts on crash. Use it instead of
running `run_ingest` straight from `lifespan` when you want the backend
running 24/7 but only consuming the broker feed during market hours.

Holidays default to a small built-in list; override by editing
`NSE_HOLIDAYS` or shipping a YAML file via NSE_HOLIDAYS_PATH env var
(format: one ISO date per line).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, time
from pathlib import Path
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# Built-in NSE holidays for the trailing/leading 12 months. Refresh annually
# from https://www.nseindia.com/resources/exchange-communication-holidays
NSE_HOLIDAYS: set[date] = {
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 6),   # Holi
    date(2026, 3, 31),  # Eid-ul-Fitr
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Mahavir Jayanti / Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 8, 15),  # Independence Day
    date(2026, 9, 7),   # Ganesh Chaturthi
    date(2026, 10, 2),  # Gandhi Jayanti
    date(2026, 10, 21), # Diwali Laxmi Pujan (muhurat — half day; treat as off)
    date(2026, 11, 4),  # Diwali Balipratipada
    date(2026, 11, 25), # Guru Nanak Jayanti
    date(2026, 12, 25), # Christmas
}


def _load_holidays() -> set[date]:
    extra = os.environ.get("NSE_HOLIDAYS_PATH")
    if not extra:
        return set(NSE_HOLIDAYS)
    p = Path(extra)
    if not p.exists():
        log.warning("NSE_HOLIDAYS_PATH set but file missing: %s", p)
        return set(NSE_HOLIDAYS)
    out = set(NSE_HOLIDAYS)
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.add(date.fromisoformat(line))
        except ValueError:
            log.warning("bad holiday date: %r", line)
    return out


def _now_ist() -> datetime:
    return datetime.now(IST)


def _is_trading_day(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 5 and d not in holidays


def _seconds_until(target: datetime, now: datetime) -> float:
    return max(0.0, (target - now).total_seconds())


def _next_market_open(now: datetime, holidays: set[date]) -> datetime:
    """Return the next datetime when the market opens, IST."""
    candidate = now.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
    if now.timetz() >= MARKET_CLOSE.replace(tzinfo=IST) or not _is_trading_day(now.date(), holidays):
        # Roll forward to next day.
        from datetime import timedelta

        candidate += timedelta(days=1)
    while not _is_trading_day(candidate.date(), holidays):
        from datetime import timedelta

        candidate += timedelta(days=1)
    if candidate.time() < MARKET_OPEN:
        candidate = candidate.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
    return candidate


def is_market_open(now: datetime | None = None, holidays: set[date] | None = None) -> bool:
    now = now or _now_ist()
    holidays = holidays if holidays is not None else _load_holidays()
    if not _is_trading_day(now.date(), holidays):
        return False
    return MARKET_OPEN <= now.timetz().replace(tzinfo=None) < MARKET_CLOSE


async def market_hours_loop(
    ingest_factory: Callable[[], Awaitable[None]],
    *,
    poll_s: float = 30.0,
) -> None:
    """Run `ingest_factory()` only while the market is open.

    `ingest_factory` should be a coroutine factory that connects to the feed
    and returns when disconnected; we cancel it when the market closes.
    """
    holidays = _load_holidays()
    log.info("market-hours scheduler started (loaded %d holidays)", len(holidays))

    while True:
        now = _now_ist()
        if is_market_open(now, holidays):
            log.info("market open — starting ingest")
            ingest_task = asyncio.create_task(ingest_factory(), name="ingest-window")
            try:
                while is_market_open(_now_ist(), holidays):
                    if ingest_task.done():
                        # Crashed or returned; log and reschedule for the next poll.
                        exc = ingest_task.exception()
                        if exc:
                            log.warning("ingest crashed in-window: %s", exc)
                        else:
                            log.info("ingest returned cleanly in-window; restarting")
                        ingest_task = asyncio.create_task(ingest_factory(), name="ingest-window")
                    await asyncio.sleep(poll_s)
            finally:
                if not ingest_task.done():
                    log.info("market closed — stopping ingest")
                    ingest_task.cancel()
                    try:
                        await ingest_task
                    except (asyncio.CancelledError, Exception):
                        pass
        # Sleep until the next market open.
        opens_at = _next_market_open(_now_ist(), holidays)
        wait = _seconds_until(opens_at, _now_ist())
        log.info("market closed; sleeping %.0fs until %s IST", wait, opens_at.isoformat())
        # Cap sleep at 1h so daily-changing config or holiday updates take effect.
        await asyncio.sleep(min(wait, 3600.0))
