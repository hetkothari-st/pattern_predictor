"""Drift report sanity tests."""
from __future__ import annotations

import pytest
from sqlmodel import SQLModel, create_engine

import app.learning.outcomes as out_mod
from app.drift import report
from app.messages import AnchorPoint, Detection


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'preds.sqlite'}"
    eng = create_engine(db_url, echo=False)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(out_mod, "_engine", eng)
    yield eng
    monkeypatch.setattr(out_mod, "_engine", None)


def _det(idx: int, pattern: str, direction: str = "bearish") -> Detection:
    return Detection(
        id=f"det-{pattern}-{idx}",
        pattern=pattern,
        direction=direction,  # type: ignore[arg-type]
        status="completed",
        confidence=0.7,
        start_ts=0.0,
        end_ts=float(idx * 60),
        anchors=[AnchorPoint(ts=float(idx * 60), price=100.0, label="x")],
    )


def _log_with_outcome(symbol: str, pattern: str, idx: int, success: bool) -> None:
    eng = out_mod._engine
    out_mod.log_detection(symbol, "1m", _det(idx, pattern))
    from sqlmodel import Session, select

    with Session(eng) as s:
        row = s.exec(select(out_mod.PredictionRow).where(out_mod.PredictionRow.det_id == f"det-{pattern}-{idx}")).first()
        row.success = success
        row.realised_move_pct = -0.01 if success else 0.01
        s.add(row)
        s.commit()


def test_drift_skips_patterns_with_too_little_history(fresh_db):
    for i in range(5):
        _log_with_outcome("X", "head_and_shoulders", i, True)
    r = report(recent_n=50, threshold=0.10)
    assert r["patterns"] == {}
    assert r["drift_count"] == 0


def test_drift_flags_drop(fresh_db):
    # Baseline: 100 mostly hits (~80% precision)
    for i in range(100):
        _log_with_outcome("X", "head_and_shoulders", i, success=(i % 5 != 0))  # 80%
    # Recent: 50 mostly misses (~20%)
    for i in range(100, 150):
        _log_with_outcome("X", "head_and_shoulders", i, success=(i % 5 == 0))  # 20%
    r = report(recent_n=50, threshold=0.10)
    entry = r["patterns"]["head_and_shoulders"]
    assert entry["baseline_precision"] >= 0.7
    assert entry["recent_precision"] <= 0.3
    assert entry["delta"] < -0.10
    assert entry["drift"] is True
    assert r["drift_count"] == 1


def test_drift_no_alert_when_steady(fresh_db):
    for i in range(150):
        _log_with_outcome("X", "double_top", i, success=(i % 3 != 0))  # ~67% throughout
    r = report(recent_n=50, threshold=0.10)
    entry = r["patterns"]["double_top"]
    assert abs(entry["delta"]) < 0.10
    assert entry["drift"] is False
    assert r["drift_count"] == 0
