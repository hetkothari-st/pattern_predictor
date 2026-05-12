"""Symbol catalog surfaced to the UI dropdown.

Indices come hardcoded (small list, stable). If `mt_subscriptions` adds more
tokens, those surface here too so the user can switch to whatever the engine
is actually receiving ticks for.
"""
from __future__ import annotations

import json
import logging

from .config import settings

log = logging.getLogger(__name__)

INDICES: list[dict] = [
    {"symbol": "NIFTY50", "label": "NIFTY 50", "tkn": "26000", "xchg": "NSE", "feed_type": 1, "group": "Index"},
    {"symbol": "NIFTYBANK", "label": "NIFTY Bank", "tkn": "26009", "xchg": "NSE", "feed_type": 1, "group": "Index"},
    {"symbol": "FINNIFTY", "label": "FIN Nifty", "tkn": "26037", "xchg": "NSE", "feed_type": 1, "group": "Index"},
    {"symbol": "SENSEX", "label": "Sensex", "tkn": "1", "xchg": "BSE", "feed_type": 1, "group": "Index"},
]


def _from_subscriptions() -> list[dict]:
    raw = settings.mt_subscriptions.strip()
    if not raw:
        return []
    try:
        subs = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("mt_subscriptions is not valid JSON; ignoring for catalog.")
        return []
    if not isinstance(subs, list):
        return []
    out = []
    for s in subs:
        if not isinstance(s, dict):
            continue
        symbol = s.get("Symbol")
        if not symbol:
            continue
        out.append(
            {
                "symbol": symbol,
                "label": s.get("Label") or symbol,
                "tkn": str(s.get("Tkn", "")),
                "xchg": s.get("Xchg", "NSE"),
                "feed_type": int(s.get("FeedType", 1)),
                "group": "Subscribed",
            }
        )
    return out


def list_symbols() -> list[dict]:
    """Indices first, then anything explicitly subscribed in the env, deduped
    on (symbol, xchg)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for entry in INDICES + _from_subscriptions():
        key = (entry["symbol"], entry["xchg"])
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out
