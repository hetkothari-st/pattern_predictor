"""Ensemble fusion sanity tests."""
from __future__ import annotations

from app.ensemble import FusionInputs, fuse, higher_tf_alignment, volume_ratio
from app.messages import Bar


def _bar(ts: float, close: float, volume: float = 1.0) -> Bar:
    return Bar(symbol="X", tf="1m", ts=ts, open=close, high=close, low=close, close=close, volume=volume, closed=True)


def test_fuse_no_extra_signals_passes_rule_through():
    r = fuse(FusionInputs(rule_confidence=0.7))
    assert r.confidence == 0.7
    assert r.factors == {"rule": 0.7}


def test_volume_confirmation_boosts():
    r = fuse(FusionInputs(rule_confidence=0.6, volume_ratio=2.0))
    assert r.confidence > 0.6
    assert r.factors["volume"] > 1.0


def test_low_volume_drags_down():
    r = fuse(FusionInputs(rule_confidence=0.7, volume_ratio=0.3))
    assert r.confidence < 0.7
    assert r.factors["volume"] < 1.0


def test_higher_tf_contradiction_drags_down():
    r = fuse(FusionInputs(rule_confidence=0.7, higher_tf_aligned=False))
    assert r.confidence < 0.7


def test_ml_agreement_boosts():
    high = fuse(FusionInputs(rule_confidence=0.5, ml_probability=0.9))
    low = fuse(FusionInputs(rule_confidence=0.5, ml_probability=0.1))
    assert high.confidence > 0.5 > low.confidence


def test_clamp_to_one():
    r = fuse(
        FusionInputs(
            rule_confidence=0.95,
            ml_probability=1.0,
            volume_ratio=10.0,
            higher_tf_aligned=True,
        )
    )
    assert 0 <= r.confidence <= 0.99


def test_volume_ratio_returns_none_with_short_history():
    bars = [_bar(i * 60, 100, volume=1.0) for i in range(5)]
    assert volume_ratio(bars, anchor_bar_ts=240, lookback=20) is None


def test_volume_ratio_computes_against_median():
    bars = [_bar(i * 60, 100, volume=10.0) for i in range(20)]
    bars.append(_bar(20 * 60, 100, volume=30.0))
    ratio = volume_ratio(bars, anchor_bar_ts=20 * 60, lookback=20)
    assert ratio is not None
    assert abs(ratio - 3.0) < 1e-6


def test_higher_tf_alignment_bullish_uptrend():
    bars = [_bar(i * 300, 100 + i, volume=1.0) for i in range(15)]
    assert higher_tf_alignment(bars, "bullish", n=10) is True
    assert higher_tf_alignment(bars, "bearish", n=10) is False


def test_higher_tf_alignment_too_short_returns_none():
    bars = [_bar(i * 300, 100, volume=1.0) for i in range(3)]
    assert higher_tf_alignment(bars, "bullish", n=10) is None
