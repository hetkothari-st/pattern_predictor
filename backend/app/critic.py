"""LLM critic: Claude reviews a confirmed pattern and produces verdict +
explanation grounded in book passages and recent price action.

Uses prompt caching on the system prompt + frozen book passages so repeated
calls for the same pattern stay cheap. Output is constrained to a JSON
schema via structured outputs.

API key is optional. When unset, `critique()` returns a disabled verdict so
the rest of the app keeps working.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from .config import settings
from .knowledge.rag import book_insight, get_guidance
from .messages import Bar, Detection

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a careful technical-analysis advisor. The user runs a
real-time pattern detector and asks you to critique each confirmed detection.

You will be given:
- The pattern name and direction the rule detector flagged
- Recent OHLCV bars (the relevant window)
- Bulkowski Encyclopedia of Chart Patterns book passages for that pattern,
  scoped to four facets: formation, causes, next steps, outcome
- Pre-computed seed guidance (entry/target/stop rules + historical stats)

Return STRICT JSON matching the schema. Be concrete and specific to THIS chart,
not generic. Reference the book where relevant. If the price action in the
recent bars doesn't actually look like the named pattern, say so honestly:
verdict="contradicted" and explain why.

Never invent statistics; only quote numbers present in the seed guidance.
Bias toward caution: this advice may move real money."""


CRITIQUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["confirmed", "weak", "contradicted"],
            "description": "Does the recent price action actually back the detector's call?",
        },
        "confidence_adjustment": {
            "type": "number",
            "description": "Multiplier on the rule confidence (0.0 to 1.5). 1.0 = neutral, <1 = downgrade, >1 = upgrade.",
        },
        "reasoning": {
            "type": "string",
            "description": "One paragraph (≤120 words) explaining your verdict against the actual bars.",
        },
        "suggested_action": {
            "type": "string",
            "description": "Specific next step for the trader (e.g., 'wait for retest of neckline at 23,420 before short'). ≤80 words.",
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "1-3 specific risks with this trade. Each ≤30 words.",
        },
    },
    "required": ["verdict", "confidence_adjustment", "reasoning", "suggested_action", "risks"],
}


def _cache_key(pattern: str, end_ts: float, last_close: float) -> tuple[str, int, int]:
    # Bucket end_ts to the hour and last_close to the integer; same pattern at
    # the same approximate moment + price hits the cached critique.
    return (pattern, int(end_ts // 3600), int(last_close))


_critique_cache: dict[tuple[str, int, int], dict[str, Any]] = {}


@lru_cache(maxsize=1)
def _client():
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — critic disabled.")
        return None
    if not settings.anthropic_api_key:
        return None
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _bars_to_table(bars: list[Bar], n: int = 30) -> str:
    """Format the last n bars as a tight ASCII table the model can read."""
    sl = bars[-n:]
    lines = ["ts,open,high,low,close,volume"]
    for b in sl:
        lines.append(f"{int(b.ts)},{b.open:.4f},{b.high:.4f},{b.low:.4f},{b.close:.4f},{b.volume:.2f}")
    return "\n".join(lines)


def _facets_block(facets: dict[str, str | None] | None) -> str:
    if not facets:
        return "(no book passages indexed)"
    parts = []
    for label, key in (("Formation", "formation"), ("Causes", "causes"),
                       ("Next steps", "next_steps"), ("Outcome", "outcome")):
        text = facets.get(key)
        if text:
            parts.append(f"### {label}\n{text}")
    return "\n\n".join(parts) if parts else "(no usable passages)"


def critique(detection: Detection, bars: list[Bar]) -> dict[str, Any]:
    """Synchronous call. Returns a verdict dict matching CRITIQUE_SCHEMA, or a
    disabled stub when the SDK / key is missing."""
    client = _client()
    if client is None:
        return {
            "enabled": False,
            "verdict": "weak",
            "confidence_adjustment": 1.0,
            "reasoning": "LLM critic disabled — set ANTHROPIC_API_KEY in backend/.env to enable.",
            "suggested_action": "Follow the seed guidance shown above.",
            "risks": ["Critic offline; no second-opinion analysis available."],
        }

    last_close = bars[-1].close if bars else 0.0
    key = _cache_key(detection.pattern, detection.end_ts, last_close)
    cached = _critique_cache.get(key)
    if cached is not None:
        return cached

    facets = book_insight(detection.pattern)
    guidance = get_guidance(detection.pattern) or {}
    user_text = (
        f"Pattern: {detection.pattern} ({detection.direction}, status={detection.status}, "
        f"rule confidence {detection.confidence:.2f})\n"
        f"Notes from detector: {detection.notes or '(none)'}\n\n"
        f"Recent bars (most recent last):\n{_bars_to_table(bars)}\n\n"
        f"Seed guidance from patterns.yaml:\n"
        f"  Entry rule: {guidance.get('entry_rule', '?')}\n"
        f"  Target rule: {guidance.get('target_rule', '?')}\n"
        f"  Stop rule: {guidance.get('stop_rule', '?')}\n"
        f"  Historical: {int(guidance.get('success_rate', 0) * 100)}% success, "
        f"avg move {int(guidance.get('avg_move', 0) * 100)}%, "
        f"throwback {int(guidance.get('throwback_pct', 0) * 100)}%\n\n"
        f"Bulkowski book passages:\n{_facets_block(facets)}"
    )
    try:
        response = client.messages.create(
            model=settings.critic_model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": CRITIQUE_SCHEMA,
                }
            },
            messages=[{"role": "user", "content": user_text}],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("critic call failed: %s", exc)
        return {
            "enabled": True,
            "verdict": "weak",
            "confidence_adjustment": 1.0,
            "reasoning": f"Critic error: {exc}",
            "suggested_action": "Defer to seed guidance.",
            "risks": ["Critic returned an error this turn."],
        }

    import json

    text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {
            "verdict": "weak",
            "confidence_adjustment": 1.0,
            "reasoning": "Could not parse critic output.",
            "suggested_action": "Defer to seed guidance.",
            "risks": ["Critic returned non-JSON."],
        }
    parsed["enabled"] = True
    _critique_cache[key] = parsed
    # Bound cache size; FIFO eviction.
    if len(_critique_cache) > 256:
        for k in list(_critique_cache.keys())[:64]:
            _critique_cache.pop(k, None)
    return parsed
