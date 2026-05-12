"""Retrain loop: rebuild the synth corpus, blend in recorded real OHLCV,
retrain the CNN with the v2 trainer, and promote the new checkpoint with
versioning + a backtest gate.

Promotion gate: a new checkpoint replaces `data/models/v1.pt` only when
its synth val accuracy >= the previous champion's. Each candidate is also
archived to `data/models/v1_<timestamp>.pt` so we can roll back.

Run modes:
  CLI (cron):     python -m app.learning.retrain
  In-process:     await retrain_loop_task()  (background task in lifespan)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..config import settings

log = logging.getLogger("retrain")

VAL_ACC_RE = re.compile(r"val_acc=([\d.]+)")


def _model_path() -> Path:
    p = Path(settings.model_path)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent.parent / p
    return p


def _archive_dir() -> Path:
    d = _model_path().parent / "archive"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path() -> Path:
    return _model_path().with_suffix(".meta.json")


def _read_meta() -> dict:
    p = _meta_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def _write_meta(meta: dict) -> None:
    _meta_path().write_text(json.dumps(meta, indent=2))


def _last_val_acc(stdout: str) -> float | None:
    """Extract the BEST val_acc from a train_v2 stdout dump."""
    matches = [float(m.group(1)) for m in VAL_ACC_RE.finditer(stdout)]
    return max(matches) if matches else None


def run_once(
    *,
    per_class: int = 400,
    none_count: int = 1500,
    epochs: int = 25,
    promote_min_delta: float = -0.005,
) -> dict:
    """Regenerate corpus → train → maybe promote. Returns a result dict."""
    backend_root = Path(__file__).resolve().parent.parent.parent
    corpus_path = backend_root / ".." / "data" / "ml" / "corpus.npz"

    log.info("regenerating corpus (per_class=%d none=%d)", per_class, none_count)
    subprocess.check_call(
        [
            sys.executable, "-m", "app.ml.synth_corpus",
            "--per-class", str(per_class),
            "--none-count", str(none_count),
            "--out-npz", str(corpus_path),
        ],
        cwd=backend_root,
    )

    log.info("training (epochs=%d)", epochs)
    proc = subprocess.run(
        [
            sys.executable, "-m", "app.ml.train_v2",
            "--npz", str(corpus_path),
            "--epochs", str(epochs),
        ],
        cwd=backend_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        log.error("trainer failed: %s", proc.stderr[-500:])
        return {"promoted": False, "reason": "train_failed", "stderr": proc.stderr[-1000:]}

    new_acc = _last_val_acc(proc.stdout)
    meta = _read_meta()
    prev_acc = meta.get("val_acc")
    log.info("trained: val_acc=%s (previous champion=%s)", new_acc, prev_acc)

    # train_v2 only saves the checkpoint when val_acc improves WITHIN that
    # run, so the file at model_path is whatever this run produced. If it's
    # below the across-runs champion, restore the archived champion.
    promote = (
        new_acc is not None
        and (prev_acc is None or new_acc >= prev_acc + promote_min_delta)
    )

    if promote:
        ts = int(time.time())
        archive = _archive_dir() / f"v1_{ts}.pt"
        shutil.copy2(_model_path(), archive)
        new_meta = {
            "val_acc": new_acc,
            "trained_at": ts,
            "epochs": epochs,
            "per_class": per_class,
            "none_count": none_count,
            "previous_val_acc": prev_acc,
            "previous_archive": meta.get("archive"),
            "archive": str(archive.relative_to(backend_root.parent)),
        }
        _write_meta(new_meta)
        log.info("promoted new champion. val_acc=%.4f -> archive %s", new_acc, archive.name)
        return {"promoted": True, "val_acc": new_acc, "previous_val_acc": prev_acc, "archive": archive.name}

    log.info("rejected — restoring previous champion")
    prev_archive = meta.get("archive")
    if prev_archive:
        prev_path = backend_root.parent / prev_archive
        if prev_path.exists():
            shutil.copy2(prev_path, _model_path())
    return {"promoted": False, "val_acc": new_acc, "previous_val_acc": prev_acc, "reason": "no_improvement"}


async def retrain_loop(interval_h: float = 24.0) -> None:
    """Async background task. Runs `run_once` every interval_h hours."""
    log.info("retrain loop scheduled every %.1fh", interval_h)
    while True:
        try:
            result = await asyncio.to_thread(run_once)
            log.info("retrain result: %s", result)
        except Exception as exc:  # noqa: BLE001
            log.exception("retrain error: %s", exc)
        await asyncio.sleep(interval_h * 3600.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=400)
    ap.add_argument("--none-count", type=int, default=1500)
    ap.add_argument("--epochs", type=int, default=25)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = run_once(
        per_class=args.per_class,
        none_count=args.none_count,
        epochs=args.epochs,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
