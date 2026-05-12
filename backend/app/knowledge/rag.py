"""Pattern guidance lookup. Reads `patterns.yaml` and optionally augments with
RAG-retrieved prose once the book has been ingested.

Today: pure YAML lookup. The Chroma path is left as a stub so the network /
embedding install can stay optional. When `ingest_book.py` is run, it writes
richer prose into `patterns.yaml` under each pattern key.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config import settings


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, Any]]:
    path = Path(settings.patterns_yaml)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def get_guidance(pattern: str) -> dict[str, Any] | None:
    data = _load().get(pattern)
    if data is None:
        return None
    return {
        "pattern": pattern,
        "summary": data.get("summary", ""),
        "entry_rule": data.get("entry_rule", ""),
        "target_rule": data.get("target_rule", ""),
        "stop_rule": data.get("stop_rule", ""),
        "success_rate": float(data.get("success_rate", 0.0)),
        "avg_move": float(data.get("avg_move", 0.0)),
        "throwback_pct": float(data.get("throwback_pct", 0.0)),
        "source_quote": data.get("source_quote", ""),
    }


def known_patterns() -> list[str]:
    return list(_load().keys())
