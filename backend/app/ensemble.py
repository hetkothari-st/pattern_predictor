"""Ensemble confidence fusion.

A detection's headline confidence is what the rule detector said, but real
agreement across (rule, ML, volume confirmation, multi-TF agreement) is a
much better predictor of follow-through. This module adjusts the rule
confidence using cheap signals available at detection time, and exposes a
breakdown so the UI can show *why* a confidence moved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .messages import Bar, Detection


@dataclass
class FusionInputs:
    rule_confidence: float
    ml_probability: float | None = None
    volume_ratio: float | None = None  # breakout-bar volume / median(last 20)
    higher_tf_aligned: bool | None = None  # 5m or 15m trend agrees with direction


@dataclass
class FusionResult:
    confidence: float
    factors: dict[str, float] = field(default_factory=dict)


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def volume_ratio(bars: list[Bar], anchor_bar_ts: float, lookback: int = 20) -> float | None:
    """Volume of the bar at anchor_bar_ts divided by the median of the prior
    `lookback` bars. Returns None if not enough history."""
    if len(bars) < lookback + 1:
        return None
    target = next((b for b in reversed(bars) if abs(b.ts - anchor_bar_ts) < 1e-6), None)
    if target is None:
        return None
    idx = bars.index(target)
    prior = [b.volume for b in bars[max(0, idx - lookback):idx] if b.volume > 0]
    if not prior:
        return None
    med = _median(prior)
    if med <= 0:
        return None
    return target.volume / med


def higher_tf_alignment(
    higher_bars: Iterable[Bar],
    direction: str,
    n: int = 10,
) -> bool | None:
    """Heuristic: true if the last n closes on the higher TF show a slope
    that agrees with `direction`. None if not enough higher-TF bars yet."""
    bars = list(higher_bars)
    if len(bars) < n:
        return None
    closes = [b.close for b in bars[-n:]]
    slope = closes[-1] - closes[0]
    if abs(slope) < 1e-9:
        return False
    if direction == "bullish":
        return slope > 0
    if direction == "bearish":
        return slope < 0
    return False


def fuse(inputs: FusionInputs) -> FusionResult:
    """Multiplicative blend.
    - rule_confidence is the base
    - ML agreement (>0.5 prob for the same pattern) → +
    - Volume confirmation (ratio >= 1.3) → +, weak (ratio < 0.6) → -
    - Higher-TF alignment → +, contradiction → -
    Result clamped to [0, 0.99].
    """
    factors: dict[str, float] = {"rule": float(inputs.rule_confidence)}
    score = float(inputs.rule_confidence)

    if inputs.ml_probability is not None:
        ml_factor = 1.0 + 0.4 * (inputs.ml_probability - 0.5)
        ml_factor = max(0.7, min(1.3, ml_factor))
        score *= ml_factor
        factors["ml"] = ml_factor

    if inputs.volume_ratio is not None:
        if inputs.volume_ratio >= 1.3:
            v_factor = 1.15
        elif inputs.volume_ratio < 0.6:
            v_factor = 0.75
        else:
            v_factor = 1.0
        score *= v_factor
        factors["volume"] = v_factor

    if inputs.higher_tf_aligned is True:
        score *= 1.15
        factors["higher_tf"] = 1.15
    elif inputs.higher_tf_aligned is False:
        score *= 0.7
        factors["higher_tf"] = 0.7

    score = max(0.0, min(0.99, score))
    return FusionResult(confidence=score, factors=factors)


def apply_to_detection(
    d: Detection,
    bars: list[Bar],
    *,
    ml_probability: float | None = None,
    higher_bars: list[Bar] | None = None,
) -> FusionResult:
    anchor_ts = d.anchors[-1].ts if d.anchors else (bars[-1].ts if bars else 0.0)
    vol = volume_ratio(bars, anchor_ts)
    hi_align = (
        higher_tf_alignment(higher_bars, d.direction)
        if higher_bars is not None
        else None
    )
    return fuse(
        FusionInputs(
            rule_confidence=d.confidence,
            ml_probability=ml_probability,
            volume_ratio=vol,
            higher_tf_aligned=hi_align,
        )
    )
