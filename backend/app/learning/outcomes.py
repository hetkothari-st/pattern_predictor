"""Log every detection emission. After N bars, score the realised move
against the predicted direction so the model's *actual* track record is
visible (and feeds retraining).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlmodel import Field, Session, SQLModel, create_engine, select

from ..config import settings
from ..messages import Detection

_engine = None


class PredictionRow(SQLModel, table=True):
    __tablename__ = "predictions"
    id: int | None = Field(default=None, primary_key=True)
    det_id: str = Field(index=True)
    symbol: str = Field(index=True)
    tf: str
    pattern: str = Field(index=True)
    direction: str
    status: str
    confidence: float
    source: str
    start_ts: float
    end_ts: float
    logged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    realised_move_pct: float | None = None
    success: bool | None = None  # set by score_outcomes


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.predictions_db, echo=False)
        SQLModel.metadata.create_all(_engine)
    return _engine


def log_detection(symbol: str, tf: str, d: Detection) -> None:
    eng = _get_engine()
    with Session(eng) as s:
        s.add(
            PredictionRow(
                det_id=d.id,
                symbol=symbol,
                tf=tf,
                pattern=d.pattern,
                direction=d.direction,
                status=d.status,
                confidence=d.confidence,
                source=d.source,
                start_ts=d.start_ts,
                end_ts=d.end_ts,
            )
        )
        s.commit()


def score_outcomes(symbol: str, tf: str, bars: Iterable, *, lookahead: int = 20) -> int:
    """Walk unfinished `completed` predictions; if enough bars have elapsed,
    measure the realised move and mark success.
    """
    bar_list = list(bars)
    by_ts = {b.ts: i for i, b in enumerate(bar_list)}
    n_scored = 0
    eng = _get_engine()
    with Session(eng) as s:
        rows = s.exec(
            select(PredictionRow).where(
                PredictionRow.symbol == symbol,
                PredictionRow.tf == tf,
                PredictionRow.status == "completed",
                PredictionRow.success.is_(None),  # type: ignore[union-attr]
            )
        ).all()
        for r in rows:
            anchor_idx = by_ts.get(r.end_ts)
            if anchor_idx is None or anchor_idx + lookahead >= len(bar_list):
                continue
            entry = bar_list[anchor_idx].close
            future = bar_list[anchor_idx + lookahead].close
            move = (future - entry) / max(1e-9, abs(entry))
            r.realised_move_pct = float(move)
            r.success = bool(
                (r.direction == "bullish" and move > 0)
                or (r.direction == "bearish" and move < 0)
            )
            s.add(r)
            n_scored += 1
        s.commit()
    return n_scored
