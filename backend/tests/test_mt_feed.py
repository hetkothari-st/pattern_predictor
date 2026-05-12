"""MT Data Feed packet parsing — pure-function tests (no socket)."""
from __future__ import annotations

from app.mt_feed import _ticks_from_packet


def test_index_data_with_token():
    packet = {"Tkn": "26000", "Symbol": "NIFTY50", "Price": 25800.5}
    ticks = _ticks_from_packet("IndexData", packet, {"26000": "NIFTY50"})
    assert len(ticks) == 1
    assert ticks[0].symbol == "NIFTY50"
    assert ticks[0].price == 25800.5


def test_index_data_symbol_fallback():
    packet = {"Symbol": "NIFTY 50", "ltp": 25801.0}
    ticks = _ticks_from_packet("IndexData", packet, {})
    assert len(ticks) == 1
    assert ticks[0].symbol == "NIFTY 50"  # original Symbol kept; token resolved internally
    assert ticks[0].price == 25801.0


def test_depth_data_mid_price():
    packet = {
        "Tkn": "55555",
        "depths": [
            {"BP": 100.0, "BQ": 200, "SP": 102.0, "SQ": 300},
            {"BP": 99.5, "BQ": 100, "SP": 102.5, "SQ": 150},
        ],
    }
    ticks = _ticks_from_packet("DepthData", packet, {"55555": "NIFTY 25800 CE"})
    assert len(ticks) == 1
    assert ticks[0].symbol == "NIFTY 25800 CE"
    assert ticks[0].price == 101.0
    assert ticks[0].volume == 500


def test_depth_data_one_sided():
    packet = {"Tkn": "1", "depths": [{"BP": 80.0, "BQ": 5}]}
    ticks = _ticks_from_packet("DepthData", packet, {"1": "X"})
    assert len(ticks) == 1
    assert ticks[0].price == 80.0


def test_unknown_token_dropped():
    packet = {"Symbol": "RANDOM", "Price": 1.0}
    ticks = _ticks_from_packet("IndexData", packet, {})
    assert ticks == []


def test_ignored_message_type():
    ticks = _ticks_from_packet("Touchline", {"Tkn": "26000"}, {"26000": "NIFTY50"})
    assert ticks == []
