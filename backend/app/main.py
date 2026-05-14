"""FastAPI entrypoint: live price ingest task + frontend WS endpoint."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from sqlmodel import Session, func, select

from .bars import store
from .config import settings
from .critic import critique
from .drift import report as drift_report
from .history import bars_in_range, day_to_range, period_to_range, trading_days
from .knowledge.rag import book_insight, get_guidance
from .learning.outcomes import PredictionRow, _get_engine
from .messages import Tick, WSOut
from .state import engine
from .symbols import list_symbols
from .ws_broadcast import hub
from .ws_ingest import run_ingest

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def sink(tick):
        await engine.on_tick(tick, tf=settings.default_timeframe)

    tasks: list[asyncio.Task] = []
    if settings.price_ws_url:
        if settings.market_hours_only:
            from .scheduler import market_hours_loop

            async def factory():
                await run_ingest(sink)

            tasks.append(
                asyncio.create_task(market_hours_loop(factory), name="market-hours-ingest")
            )
            log.info("price ingest gated by NSE market hours (09:15–15:30 IST)")
        else:
            tasks.append(asyncio.create_task(run_ingest(sink), name="price-ingest"))
    else:
        from .demo_feed import run_demo

        tasks.append(asyncio.create_task(run_demo(sink), name="demo-feed"))

    if settings.retrain_enabled:
        from .learning.retrain import retrain_loop

        tasks.append(
            asyncio.create_task(
                retrain_loop(interval_h=settings.retrain_interval_h),
                name="retrain-loop",
            )
        )
        log.info("retrain loop enabled (every %.1fh)", settings.retrain_interval_h)

    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="Chart Pattern Intelligence", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/api/symbols")
async def symbols() -> dict:
    return {"items": list_symbols()}


@app.get("/api/insight")
async def insight(pattern: str = Query(...)) -> dict:
    """Book-derived RAG insight for the given pattern. Empty {} if Chroma
    isn't loaded yet."""
    facets = book_insight(pattern) or {}
    return {"pattern": pattern, "facets": facets}


@app.get("/api/drift")
async def drift(recent_n: int = Query(50), threshold: float = Query(0.10)) -> dict:
    """Per-pattern precision drift over the predictions log."""
    return drift_report(recent_n=recent_n, threshold=threshold)


@app.get("/api/critique")
async def critique_endpoint(
    symbol: str = Query(...),
    tf: str = Query("1m"),
    pattern: str = Query(...),
) -> dict:
    """Run the LLM critic against the most recent detection of the given
    pattern in this stream. Falls back to a disabled stub if no API key is
    set or no matching detection exists."""
    memo = engine._memo_for(symbol, tf)
    target = next(
        (d for d in memo.active.values() if d.pattern == pattern),
        None,
    )
    if target is None:
        return {"available": False, "reason": "No active detection for this pattern."}
    bars = store.get(symbol, tf).snapshot()
    verdict = critique(target, bars)
    return {"available": True, "pattern": pattern, **verdict}


@app.get("/api/bars")
async def bars(symbol: str = Query(...), tf: str = Query("1m")) -> dict:
    stream = store.get(symbol, tf)
    return {"bars": [b.model_dump() for b in stream.snapshot()]}


@app.get("/api/bars/range")
async def bars_range(
    symbol: str = Query(...),
    tf: str = Query("1m"),
    day: str | None = Query(None, description="YYYY-MM-DD (IST)"),
    period: str | None = Query(None, description="1d|7d|30d|90d|1y"),
    start_ts: float | None = Query(None),
    end_ts: float | None = Query(None),
) -> dict:
    """Return historical bars from the recorded CSV in a date window.
    Resolution priority: explicit start_ts/end_ts > day > period."""
    if day:
        start_ts, end_ts = day_to_range(day)
    elif period:
        try:
            start_ts, end_ts = period_to_range(period)
        except ValueError as exc:
            return {"error": str(exc), "bars": []}
    bars = bars_in_range(symbol, tf, start_ts, end_ts)
    return {
        "symbol": symbol,
        "tf": tf,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "bars": [b.model_dump() for b in bars],
    }


@app.get("/api/days")
async def days(
    symbol: str = Query(...),
    tf: str = Query("1m"),
    limit: int = Query(60),
) -> dict:
    """Return up to `limit` recent IST calendar days for which we have
    recorded bars. Newest first."""
    return {"symbol": symbol, "tf": tf, "days": trading_days(symbol, tf, limit=limit)}


@app.get("/api/watchlist")
async def watchlist() -> dict:
    """Return all (symbol, tf) streams the engine has seen, plus the
    highest-confidence active detection per stream so the sidebar can show
    a live status dot per symbol.
    """
    items = []
    for (symbol, tf), _stream in store._streams.items():  # type: ignore[attr-defined]
        memo = engine._memo_for(symbol, tf)
        active = list(memo.active.values())
        top = max(active, key=lambda d: d.confidence, default=None)
        items.append(
            {
                "symbol": symbol,
                "tf": tf,
                "top_pattern": top.pattern if top else None,
                "top_direction": top.direction if top else None,
                "top_confidence": top.confidence if top else None,
                "top_status": top.status if top else None,
            }
        )
    items.sort(key=lambda x: (x["symbol"], x["tf"]))
    return {"items": items}


@app.post("/api/tick")
async def post_tick(tick: Tick, tf: str = Query("1m")) -> dict:
    """Inject a tick into the running engine. Used by the replay tool and any
    external producer that doesn't speak the WS ingest protocol.
    """
    await engine.on_tick(tick, tf=tf)
    return {"ok": True}


@app.get("/api/performance")
async def performance() -> dict:
    """Per-pattern rolling track record. Powers the UI's "model performance" page."""
    eng = _get_engine()
    with Session(eng) as s:
        rows = s.exec(
            select(
                PredictionRow.pattern,
                func.count().label("n"),
                func.sum(func.case((PredictionRow.success.is_(True), 1), else_=0)).label("hits"),
            )
            .where(PredictionRow.success.is_not(None))
            .group_by(PredictionRow.pattern)
        ).all()
    return {
        "by_pattern": [
            {"pattern": r[0], "n": int(r[1]), "hits": int(r[2] or 0), "precision": (r[2] or 0) / max(1, r[1])}
            for r in rows
        ],
    }


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket, symbol: str = Query(...), tf: str = Query("1m")) -> None:
    await ws.accept()
    await hub.subscribe(ws, symbol, tf)
    # Send a snapshot of existing bars + active detections so the chart paints
    # immediately and prior pattern overlays survive a page reload.
    stream = store.get(symbol, tf)
    snapshot = [b.model_dump() for b in stream.snapshot()]
    memo = engine._memo_for(symbol, tf)
    active = [d.model_dump() for d in memo.active.values()]
    guidance = []
    seen_patterns: set[str] = set()
    for d in memo.active.values():
        if d.status == "completed" and d.pattern not in seen_patterns:
            g = get_guidance(d.pattern)
            if g is not None:
                guidance.append(g)
                seen_patterns.add(d.pattern)
    await ws.send_text(
        WSOut(
            type="snapshot",
            payload={"bars": snapshot, "detections": active, "guidance": guidance},
        ).model_dump_json()
    )
    try:
        while True:
            # We don't expect client messages today; keep the connection open.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(ws, symbol, tf)
