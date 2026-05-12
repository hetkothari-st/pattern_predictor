from app.bars import BarStream
from app.messages import Tick


def test_bars_aggregate_within_bucket():
    s = BarStream(symbol="X", tf="1m")
    s.ingest(Tick(symbol="X", ts=0.0, price=100.0, volume=1.0))
    s.ingest(Tick(symbol="X", ts=30.0, price=105.0, volume=2.0))
    s.ingest(Tick(symbol="X", ts=59.0, price=102.0, volume=1.0))
    snap = s.snapshot()
    assert len(snap) == 1
    b = snap[-1]
    assert b.open == 100.0 and b.high == 105.0 and b.low == 100.0 and b.close == 102.0
    assert b.volume == 4.0 and b.closed is False


def test_bars_close_on_boundary():
    s = BarStream(symbol="X", tf="1m")
    s.ingest(Tick(symbol="X", ts=0.0, price=100.0))
    s.ingest(Tick(symbol="X", ts=60.0, price=101.0))
    snap = s.snapshot()
    assert len(snap) == 2
    assert snap[0].closed is True and snap[1].closed is False
