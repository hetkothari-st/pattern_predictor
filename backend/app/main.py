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
from .learning.outcomes import PredictionRow, _get_engine
from .messages import Tick, WSOut
from .state import engine
from .ws_broadcast import hub
from .ws_ingest import run_ingest

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def sink(tick):
        await engine.on_tick(tick, tf=settings.default_timeframe)

    task = asyncio.create_task(run_ingest(sink), name="price-ingest")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
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


@app.get("/api/bars")
async def bars(symbol: str = Query(...), tf: str = Query("1m")) -> dict:
    stream = store.get(symbol, tf)
    return {"bars": [b.model_dump() for b in stream.snapshot()]}


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
    # Send a snapshot of existing bars so the chart paints immediately.
    stream = store.get(symbol, tf)
    snapshot = [b.model_dump() for b in stream.snapshot()]
    await ws.send_text(WSOut(type="snapshot", payload={"bars": snapshot}).model_dump_json())
    try:
        while True:
            # We don't expect client messages today; keep the connection open.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(ws, symbol, tf)
