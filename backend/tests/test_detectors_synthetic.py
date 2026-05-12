"""Each detector must fire on a textbook synthetic shape."""
from __future__ import annotations

import pytest

from app.detectors.cup_handle import CupHandle
from app.detectors.double_top_bottom import DoubleTopBottom
from app.detectors.flag_pennant import FlagPennant
from app.detectors.head_shoulders import HeadAndShoulders
from app.detectors.triangle import Triangle
from app.detectors.wedge import Wedge

from . import synth


def _has(detections, pattern: str) -> bool:
    return any(d.pattern == pattern for d in detections)


def test_head_and_shoulders():
    bars = synth.head_and_shoulders()
    dets = HeadAndShoulders().detect(bars)
    assert _has(dets, "head_and_shoulders"), [d.pattern for d in dets]
    target = next(d for d in dets if d.pattern == "head_and_shoulders")
    assert target.direction == "bearish"
    labels = {a.label for a in target.anchors}
    assert {"left shoulder", "head", "right shoulder"}.issubset(labels)


def test_inverse_head_and_shoulders():
    bars = synth.inverse_head_and_shoulders()
    dets = HeadAndShoulders().detect(bars)
    assert _has(dets, "inverse_head_and_shoulders"), [d.pattern for d in dets]


def test_double_top():
    bars = synth.double_top()
    dets = DoubleTopBottom().detect(bars)
    assert _has(dets, "double_top"), [d.pattern for d in dets]


def test_double_bottom():
    bars = synth.double_bottom()
    dets = DoubleTopBottom().detect(bars)
    assert _has(dets, "double_bottom"), [d.pattern for d in dets]


@pytest.mark.parametrize(
    "factory,expected",
    [
        (synth.ascending_triangle, "ascending_triangle"),
        (synth.descending_triangle, "descending_triangle"),
        (synth.symmetric_triangle, "symmetric_triangle"),
    ],
)
def test_triangles(factory, expected):
    dets = Triangle().detect(factory())
    assert _has(dets, expected), [d.pattern for d in dets]


@pytest.mark.parametrize(
    "factory,expected",
    [
        (synth.rising_wedge, "rising_wedge"),
        (synth.falling_wedge, "falling_wedge"),
    ],
)
def test_wedges(factory, expected):
    dets = Wedge().detect(factory())
    assert _has(dets, expected), [d.pattern for d in dets]


def test_bull_flag():
    dets = FlagPennant().detect(synth.bull_flag())
    assert _has(dets, "bull_flag"), [d.pattern for d in dets]


def test_cup_with_handle():
    dets = CupHandle().detect(synth.cup_with_handle())
    assert _has(dets, "cup_with_handle"), [d.pattern for d in dets]
