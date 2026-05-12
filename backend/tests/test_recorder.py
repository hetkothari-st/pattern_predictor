"""OHLCV recorder writes a header on first append and one row per closed bar."""
from __future__ import annotations

import csv

from app.config import settings
from app.messages import Bar
from app.recorder import _seen_files, record_bar


def _bar(ts: float, *, closed: bool = True) -> Bar:
    return Bar(
        symbol="TEST_REC",
        tf="1m",
        ts=ts,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=10.0,
        closed=closed,
    )


def test_record_appends_with_header(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ohlcv_dir", str(tmp_path))
    monkeypatch.setattr(settings, "record_ohlcv", True)
    _seen_files.clear()

    record_bar(_bar(60.0))
    record_bar(_bar(120.0))

    file = tmp_path / "TEST_REC_1m.csv"
    rows = list(csv.reader(file.open()))
    assert rows[0] == ["ts", "open", "high", "low", "close", "volume"]
    assert len(rows) == 3  # header + 2 bars
    assert rows[1][0] == "60.0"
    assert rows[2][0] == "120.0"


def test_record_skips_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ohlcv_dir", str(tmp_path))
    monkeypatch.setattr(settings, "record_ohlcv", False)
    _seen_files.clear()

    record_bar(_bar(60.0))

    assert not (tmp_path / "TEST_REC_1m.csv").exists()


def test_record_skips_forming_bar(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ohlcv_dir", str(tmp_path))
    monkeypatch.setattr(settings, "record_ohlcv", True)
    _seen_files.clear()

    record_bar(_bar(60.0, closed=False))

    assert not (tmp_path / "TEST_REC_1m.csv").exists()
