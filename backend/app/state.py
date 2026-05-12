"""The engine: ticks -> bars -> detectors -> broadcast.

Maintains the last-seen detection set per stream so we can emit `forming` and
`completed` lifecycle events rather than re-firing on every bar.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import hashlib

from .bars import store
from .detectors.registry import REGISTRY
from .ensemble import apply_to_detection
from .knowledge.rag import get_guidance
from .learning.outcomes import log_detection, score_outcomes
from .messages import AnchorPoint, Bar, Detection, Tick, WSOut
from .ml import infer as ml_infer
from .recorder import record_bar
from .ws_broadcast import hub

EARLY_THRESHOLD = 0.55  # min ML probability to emit a "watching for X" signal
HIGHER_TFS: dict[str, str] = {"1m": "5m", "5m": "15m", "15m": "1h", "1h": "4h"}
# Drop completed detections whose ensemble confidence falls below this floor —
# nothing low-conviction goes to the UI.
ENSEMBLE_MIN_CONFIDENCE = 0.35
PATTERN_DIRECTION: dict[str, str] = {
    "head_and_shoulders": "bearish",
    "inverse_head_and_shoulders": "bullish",
    "double_top": "bearish",
    "double_bottom": "bullish",
    "ascending_triangle": "bullish",
    "descending_triangle": "bearish",
    "symmetric_triangle": "bullish",
    "rising_wedge": "bearish",
    "falling_wedge": "bullish",
    "bull_flag": "bullish",
    "bear_flag": "bearish",
    "cup_with_handle": "bullish",
}

log = logging.getLogger(__name__)


@dataclass
class _StreamMemo:
    active: dict[str, Detection] = field(default_factory=dict)  # id -> last emission


class Engine:
    def __init__(self) -> None:
        self._memo: dict[tuple[str, str], _StreamMemo] = {}

    def _memo_for(self, symbol: str, tf: str) -> _StreamMemo:
        key = (symbol, tf)
        if key not in self._memo:
            self._memo[key] = _StreamMemo()
        return self._memo[key]

    async def on_tick(self, tick: Tick, *, tf: str) -> None:
        stream = store.get(tick.symbol, tf)
        emitted_bars = stream.ingest(tick)
        for bar in emitted_bars:
            await hub.publish(
                tick.symbol, tf, WSOut(type="bar", payload=bar.model_dump())
            )
            if bar.closed:
                record_bar(bar)
                # Aggregate this tick into all relevant higher timeframes so
                # the multi-TF confirmation has bars to read against. Higher
                # TFs also record their own closed bars to disk so retrain
                # has multi-resolution data, not just the base TF.
                for higher_tf in HIGHER_TFS.values():
                    higher_stream = store.get(tick.symbol, higher_tf)
                    higher_emitted = higher_stream.ingest(tick)
                    for hb in higher_emitted:
                        if hb.closed:
                            record_bar(hb)
        if any(b.closed for b in emitted_bars):
            # Run detectors only on bar-close to keep CPU bounded.
            await self._run_detectors(tick.symbol, tf, stream.snapshot())

    async def _run_detectors(self, symbol: str, tf: str, bars: list[Bar]) -> None:
        memo = self._memo_for(symbol, tf)
        seen: set[str] = set()
        # Pre-compute ML probs once for this bar; ensemble reuses them.
        ml = ml_infer.infer(bars)
        # Higher-TF context — used by ensemble for confirmation alignment.
        higher_tf = HIGHER_TFS.get(tf)
        higher_bars = (
            store.get(symbol, higher_tf).snapshot() if higher_tf else None
        )

        for det_cls in REGISTRY:
            detector = det_cls()
            try:
                detections = detector.detect(bars)
            except Exception as exc:  # noqa: BLE001
                log.exception("Detector %s failed: %s", det_cls.__name__, exc)
                continue
            for d in detections:
                ml_prob = (ml or {}).get("pattern", {}).get(d.pattern) if ml else None
                fusion = apply_to_detection(
                    d, bars, ml_probability=ml_prob, higher_bars=higher_bars
                )
                # Volume / TF gate: drop completed detections we have no
                # conviction in. Forming detections still flow because the UI
                # already filters them by confidence client-side.
                if d.status == "completed" and fusion.confidence < ENSEMBLE_MIN_CONFIDENCE:
                    continue
                d = d.model_copy(
                    update={
                        "confidence": fusion.confidence,
                        "notes": (
                            d.notes
                            + (
                                f" | fusion: " + ", ".join(
                                    f"{k}×{v:.2f}" if k != "rule" else f"rule={v:.2f}"
                                    for k, v in fusion.factors.items()
                                )
                            )
                        ).strip(" |"),
                    }
                )
                seen.add(d.id)
                prev = memo.active.get(d.id)
                if prev is None or prev.status != d.status or prev.confidence != d.confidence:
                    memo.active[d.id] = d
                    await hub.publish(
                        symbol, tf, WSOut(type="detection", payload=d.model_dump())
                    )
                    if d.status == "completed" and (prev is None or prev.status != "completed"):
                        try:
                            log_detection(symbol, tf, d)
                        except Exception as exc:  # noqa: BLE001
                            log.warning("log_detection failed: %s", exc)
                        guidance = get_guidance(d.pattern)
                        if guidance is not None:
                            await hub.publish(
                                symbol, tf, WSOut(type="guidance", payload=guidance)
                            )
        # ML early-warning: emit "watching for X" when ML is confident and no
        # rule detector has already flagged this pattern. (`ml` already
        # computed once at the top of this method.)
        if ml is not None:
            covered = {memo.active[i].pattern for i in seen}
            for pattern, prob in ml["early"].items():
                if pattern == "none" or prob < EARLY_THRESHOLD or pattern in covered:
                    continue
                det_id = "ml-" + hashlib.md5(
                    f"{pattern}|{bars[-1].ts:.0f}".encode()
                ).hexdigest()[:10]
                d = Detection(
                    id=det_id,
                    pattern=pattern,
                    direction=PATTERN_DIRECTION.get(pattern, "bullish"),  # type: ignore[arg-type]
                    status="forming",
                    confidence=float(prob),
                    source="ml",
                    start_ts=float(bars[max(0, len(bars) - 60)].ts),
                    end_ts=float(bars[-1].ts),
                    anchors=[AnchorPoint(ts=float(bars[-1].ts), price=bars[-1].close, label="ML")],
                    notes="ML early-warning",
                )
                seen.add(det_id)
                memo.active[det_id] = d
                await hub.publish(symbol, tf, WSOut(type="detection", payload=d.model_dump()))

        # Score any outstanding completed predictions against the realised price action.
        try:
            score_outcomes(symbol, tf, bars)
        except Exception as exc:  # noqa: BLE001
            log.warning("score_outcomes failed: %s", exc)

        # Drop stale "forming" detections that no longer fire, and evict
        # completed detections that have aged out of the visible window —
        # otherwise overlays accumulate forever as new bars arrive.
        last_ts = float(bars[-1].ts) if bars else 0.0
        # Keep completed detections for ~60 bars worth of time after their end.
        keep_window_s = 60 * 60  # 60 minutes on a 1m chart; plenty for context
        for stale_id in list(memo.active.keys()):
            d = memo.active[stale_id]
            if stale_id not in seen and d.status == "forming":
                del memo.active[stale_id]
            elif d.status == "completed" and last_ts - d.end_ts > keep_window_s:
                del memo.active[stale_id]


engine = Engine()
