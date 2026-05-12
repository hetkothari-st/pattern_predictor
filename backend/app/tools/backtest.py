"""Walk an OHLCV CSV through every rule detector. For each `completed`
detection, measure whether price moved in the predicted direction within
LOOKAHEAD bars. Print per-pattern precision, hit count, sample size.

Usage:
    python -m app.tools.backtest --csv data/ohlcv/NIFTY50_1m.csv --lookahead 20
    python -m app.tools.backtest --csv "data/ohlcv/_synth/*.csv" --lookahead 30 --json out.json
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
from collections import defaultdict
from pathlib import Path

from ..detectors.registry import REGISTRY
from ..messages import Bar
from ..ml.train import load_csv

log = logging.getLogger("backtest")


def evaluate(bars: list[Bar], lookahead: int = 20, step: int = 5) -> dict:
    """Slide detectors across the bar history; for each completed detection,
    check whether the realised move N bars later matches predicted direction."""
    n = len(bars)
    if n < 80:
        return {"by_pattern": {}, "total": 0, "evaluated": 0}

    seen: set[str] = set()
    raw: list[dict] = []
    for end in range(50, n - lookahead, step):
        window = bars[:end]
        for det_cls in REGISTRY:
            try:
                detections = det_cls().detect(window)
            except Exception:
                continue
            for d in detections:
                if d.status != "completed" or d.id in seen:
                    continue
                seen.add(d.id)
                # Find the bar at end_ts and look ahead.
                anchor_close = window[-1].close
                future = bars[min(end + lookahead - 1, n - 1)].close
                move_pct = (future - anchor_close) / max(1e-9, abs(anchor_close))
                hit = (
                    (d.direction == "bullish" and move_pct > 0)
                    or (d.direction == "bearish" and move_pct < 0)
                )
                raw.append({
                    "pattern": d.pattern,
                    "direction": d.direction,
                    "confidence": d.confidence,
                    "move_pct": move_pct,
                    "hit": bool(hit),
                })

    by_pattern: dict[str, dict] = defaultdict(lambda: {"n": 0, "hits": 0, "moves": []})
    for r in raw:
        bp = by_pattern[r["pattern"]]
        bp["n"] += 1
        if r["hit"]:
            bp["hits"] += 1
        bp["moves"].append(r["move_pct"])

    by_pattern_out: dict[str, dict] = {}
    for pat, agg in by_pattern.items():
        n = agg["n"]
        hits = agg["hits"]
        moves = agg["moves"]
        avg_move = sum(moves) / max(1, len(moves))
        by_pattern_out[pat] = {
            "n": n,
            "hits": hits,
            "precision": hits / max(1, n),
            "avg_move_pct": avg_move,
        }

    return {
        "by_pattern": by_pattern_out,
        "total": len(raw),
        "evaluated": len(raw),
    }


def _print_table(report: dict) -> None:
    print(f"\nDetections evaluated: {report['total']}")
    if not report["by_pattern"]:
        print("  (none)")
        return
    rows = sorted(report["by_pattern"].items(), key=lambda x: -x[1]["precision"])
    print(f"\n{'pattern':<32} {'n':>5} {'hits':>5} {'precision':>10} {'avg move':>10}")
    print("-" * 72)
    for pat, agg in rows:
        print(
            f"{pat:<32} {agg['n']:>5} {agg['hits']:>5} "
            f"{agg['precision']*100:>9.1f}% {agg['avg_move_pct']*100:>9.2f}%"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV path or glob")
    ap.add_argument("--lookahead", type=int, default=20)
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--json", default=None, help="Optional path to dump JSON report")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    paths = sorted(Path(p) for p in glob.glob(args.csv))
    if not paths:
        raise SystemExit(f"no CSV matched: {args.csv}")

    aggregate: dict[str, dict] = defaultdict(lambda: {"n": 0, "hits": 0, "moves": []})
    grand_total = 0
    for p in paths:
        log.info("backtesting %s ...", p.name)
        bars = load_csv(p)
        report = evaluate(bars, lookahead=args.lookahead, step=args.step)
        grand_total += report["total"]
        for pat, agg in report["by_pattern"].items():
            ag = aggregate[pat]
            ag["n"] += agg["n"]
            ag["hits"] += agg["hits"]
            ag["moves"].extend([agg["avg_move_pct"]] * agg["n"])  # weighted avg

    final: dict[str, dict] = {}
    for pat, agg in aggregate.items():
        final[pat] = {
            "n": agg["n"],
            "hits": agg["hits"],
            "precision": agg["hits"] / max(1, agg["n"]),
            "avg_move_pct": (sum(agg["moves"]) / max(1, len(agg["moves"]))),
        }
    full_report = {"by_pattern": final, "total": grand_total, "evaluated": grand_total}
    _print_table(full_report)

    if args.json:
        Path(args.json).write_text(json.dumps(full_report, indent=2))
        log.info("wrote report to %s", args.json)


if __name__ == "__main__":
    main()
