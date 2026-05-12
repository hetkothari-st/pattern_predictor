"""Pydantic message types shared between ingest, engine, and the WS broadcast."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Tick(BaseModel):
    symbol: str
    ts: float  # unix seconds
    price: float
    volume: float = 0.0


class Bar(BaseModel):
    symbol: str
    tf: str  # "1m", "5m", ...
    ts: float  # open time, unix seconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = False  # False = current forming bar


class AnchorPoint(BaseModel):
    ts: float
    price: float
    label: str = ""  # e.g. "left shoulder"


class Detection(BaseModel):
    """One detection emission. Same id is reused as it updates / completes."""

    id: str
    pattern: str  # e.g. "head_and_shoulders"
    direction: Literal["bullish", "bearish"]
    status: Literal["forming", "completed"]
    confidence: float  # 0..1
    source: Literal["rule", "ml", "fused"] = "rule"
    start_ts: float
    end_ts: float
    anchors: list[AnchorPoint] = Field(default_factory=list)
    notes: str = ""


class WSOut(BaseModel):
    """Wire envelope sent to the frontend."""

    type: Literal["bar", "detection", "guidance", "snapshot"]
    payload: dict
