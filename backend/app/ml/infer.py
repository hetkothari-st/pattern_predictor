"""Lazy-loaded inference over the latest bars window. Returns top-k
(pattern, probability) pairs for both heads. Returns None when no model exists
yet — the engine then operates in rule-only mode.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from ..config import settings
from ..messages import Bar
from .model import PATTERN_CLASSES, build_model
from .windows import WINDOW, bars_to_window

log = logging.getLogger(__name__)

_model = None  # cached


def _load() -> Any | None:
    global _model
    if _model is not None:
        return _model
    try:
        import torch
    except ImportError:
        log.info("PyTorch not installed; ML inference disabled.")
        return None
    path = Path(settings.model_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    if not path.exists():
        log.info("Model checkpoint missing at %s; ML inference disabled.", path)
        return None
    model = build_model()
    model.load_state_dict(torch.load(path, map_location="cpu"))
    model.eval()
    _model = model
    log.info("Loaded ML model from %s", path)
    return _model


def infer(bars: list[Bar]) -> dict[str, dict[str, float]] | None:
    if len(bars) < WINDOW:
        return None
    model = _load()
    if model is None:
        return None
    import torch

    arr = bars_to_window(bars)
    if arr is None:
        return None
    x = torch.from_numpy(arr).unsqueeze(0)
    with torch.no_grad():
        pat_logits, early_logits = model(x)
    return {
        "pattern": _to_dict(pat_logits),
        "early": _to_dict(early_logits),
    }


def _to_dict(logits) -> dict[str, float]:
    import torch

    probs = torch.softmax(logits, dim=-1).squeeze(0).tolist()
    return {PATTERN_CLASSES[i]: float(p) for i, p in enumerate(probs)}
