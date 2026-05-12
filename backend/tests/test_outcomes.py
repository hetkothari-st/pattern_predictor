"""log_detection -> score_outcomes round-trip writes success/failure to DB."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.learning.outcomes as out_mod
from app.messages import AnchorPoint, Bar, Detection


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'preds.sqlite'}"
    eng = create_engine(db_url, echo=False)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(out_mod, "_engine", eng)
    yield out_mod
    monkeypatch.setattr(out_mod, "_engine", None)


def _bar(ts: float, close: float) -> Bar:
    return Bar(symbol="X", tf="1m", ts=ts, open=close, high=close, low=close, close=close, volume=1.0, closed=True)


def _det(end_ts: float, *, direction: str = "bearish") -> Detection:
    return Detection(
        id=f"abc-{end_ts}-{direction}",
        pattern="head_and_shoulders",
        direction=direction,  # type: ignore[arg-type]
        status="completed",
        confidence=0.7,
        start_ts=0.0,
        end_ts=end_ts,
        anchors=[AnchorPoint(ts=end_ts, price=100.0, label="x")],
    )


def test_log_then_score_marks_success(fresh_db):
    fresh_db.log_detection("X", "1m", _det(end_ts=300.0, direction="bearish"))
    bars = [_bar(60.0 * i, 100.0 - i) for i in range(1, 30)]  # downtrend
    n = fresh_db.score_outcomes("X", "1m", bars, lookahead=10)
    assert n == 1
    with Session(fresh_db._engine) as s:
        row = s.exec(select(fresh_db.PredictionRow)).first()
        assert row.success is True
        assert row.realised_move_pct < 0


def test_score_marks_failure_for_wrong_direction(fresh_db):
    fresh_db.log_detection("X", "1m", _det(end_ts=300.0, direction="bullish"))
    bars = [_bar(60.0 * i, 100.0 - i) for i in range(1, 30)]
    fresh_db.score_outcomes("X", "1m", bars, lookahead=10)
    with Session(fresh_db._engine) as s:
        row = s.exec(select(fresh_db.PredictionRow)).first()
        assert row.success is False


def test_score_skips_when_not_enough_lookahead(fresh_db):
    fresh_db.log_detection("X", "1m", _det(end_ts=600.0))
    bars = [_bar(60.0 * i, 100.0) for i in range(1, 12)]
    n = fresh_db.score_outcomes("X", "1m", bars, lookahead=10)
    assert n == 0
