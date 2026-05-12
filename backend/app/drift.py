"""Per-pattern drift detection over the predictions log.

Compares recent precision (last `recent_n` scored predictions) against the
baseline precision (everything before that). Flags any pattern whose recent
precision dropped by more than `threshold` from baseline.

Backed by the same SQLite the engine writes to via `learning.outcomes`.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from .learning.outcomes import PredictionRow, _get_engine

log = logging.getLogger(__name__)


def _precision(rows: list[PredictionRow]) -> tuple[int, int]:
    n = len(rows)
    hits = sum(1 for r in rows if r.success is True)
    return hits, n


def report(*, recent_n: int = 50, threshold: float = 0.10) -> dict[str, Any]:
    """Build a per-pattern drift report.

    Returns:
        {
          "patterns": {
            "head_and_shoulders": {
              "baseline_precision": 0.62, "baseline_n": 240,
              "recent_precision": 0.41, "recent_n": 50,
              "delta": -0.21, "drift": true
            }, ...
          },
          "drift_count": 1,
          "threshold": 0.10,
          "recent_n": 50,
        }
    """
    eng = _get_engine()
    out: dict[str, Any] = {
        "patterns": {},
        "drift_count": 0,
        "threshold": threshold,
        "recent_n": recent_n,
    }
    with Session(eng) as s:
        # All scored rows, ordered by id (insertion order = chronological).
        rows = s.exec(
            select(PredictionRow)
            .where(PredictionRow.success.is_not(None))  # type: ignore[union-attr]
            .order_by(PredictionRow.id)
        ).all()

    by_pattern: dict[str, list[PredictionRow]] = {}
    for r in rows:
        by_pattern.setdefault(r.pattern, []).append(r)

    for pat, items in by_pattern.items():
        if len(items) < recent_n + 5:
            continue  # not enough history yet
        recent = items[-recent_n:]
        baseline = items[:-recent_n]
        b_hits, b_n = _precision(baseline)
        r_hits, r_n = _precision(recent)
        b_prec = b_hits / max(1, b_n)
        r_prec = r_hits / max(1, r_n)
        delta = r_prec - b_prec
        is_drift = delta < -threshold
        if is_drift:
            out["drift_count"] += 1
        out["patterns"][pat] = {
            "baseline_precision": round(b_prec, 4),
            "baseline_n": b_n,
            "recent_precision": round(r_prec, 4),
            "recent_n": r_n,
            "delta": round(delta, 4),
            "drift": is_drift,
        }
    return out
