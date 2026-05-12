"""Pattern guidance lookup. Reads `patterns.yaml` for canonical seed metadata
and queries Chroma (when present) to surface book passages tagged for each
pattern.

Each detection yields four "facets" the UI shows: formation, causes, next
steps, outcome. Each facet runs a separate query against Chroma filtered to
the pattern's chunks; the highest-scoring excerpt becomes that facet's text.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config import settings

log = logging.getLogger(__name__)


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


# ----- RAG over Chroma -------------------------------------------------------

_collection = None
_collection_loaded = False


def _get_collection():
    """Lazy-load the Chroma collection. Returns None if Chroma is not
    installed or the index hasn't been built yet."""
    global _collection, _collection_loaded
    if _collection_loaded:
        return _collection
    _collection_loaded = True
    try:
        import chromadb  # type: ignore
        from chromadb.utils.embedding_functions import (  # type: ignore
            SentenceTransformerEmbeddingFunction,
        )
    except ImportError:
        log.info("chromadb not installed; book RAG disabled.")
        return None
    path = Path(settings.chroma_dir)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    if not path.exists():
        log.info("Chroma index missing at %s; book RAG disabled.", path)
        return None
    try:
        client = chromadb.PersistentClient(path=str(path))
        _collection = client.get_or_create_collection(
            name=settings.chroma_collection,
            embedding_function=SentenceTransformerEmbeddingFunction(),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not open Chroma collection: %s", exc)
        _collection = None
    return _collection


# Per-facet queries. Each finds the chunks Bulkowski uses to discuss that
# aspect of the pattern. Different phrasings let us hit the right paragraphs
# even though the parser doesn't pre-segment them.
FACET_QUERIES: dict[str, str] = {
    "formation": "how the pattern forms identification price action shape recognition",
    "causes": "psychology behind the pattern why traders cause this market behavior",
    "next_steps": "trading tactics entry stop target measure rule what to do after breakout",
    "outcome": "performance statistics success failure rate throwback pullback historical results",
}


def _clean_excerpt(raw: str, max_chars: int = 480) -> str:
    """Trim PDF chrome (Figure / Table / page-num lines) and cap length."""
    lines = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith(("figure ", "table ", "chapter ", "page ")):
            continue
        # Lines dominated by digits = price/axis chrome.
        letters = sum(c.isalpha() for c in s)
        if len(s) > 5 and letters / len(s) < 0.55:
            continue
        lines.append(s)
    text = " ".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return text


def book_insight(pattern: str) -> dict[str, str | None] | None:
    """Return {facet: excerpt} for the given pattern, or None if RAG offline."""
    coll = _get_collection()
    if coll is None:
        return None
    out: dict[str, str | None] = {}
    for facet, query in FACET_QUERIES.items():
        try:
            res = coll.query(
                query_texts=[query],
                n_results=4,
                where={"pattern": pattern},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Chroma query failed (%s/%s): %s", pattern, facet, exc)
            out[facet] = None
            continue
        docs = (res.get("documents") or [[]])[0]
        text = next((_clean_excerpt(d) for d in docs if d and len(d.strip()) > 60), None)
        out[facet] = text
    return out
