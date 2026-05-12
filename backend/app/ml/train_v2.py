"""Robust trainer: reads the directly-labeled corpus npz, balances classes,
applies class-weighted loss, dropout, weight decay, early stopping, and
prints a per-class accuracy + confusion matrix at the end so we can see
which classes are still confused.

Usage:
    python -m app.ml.synth_corpus --per-class 400 --none-count 1200
    python -m app.ml.train_v2 --npz ../data/ml/corpus.npz --epochs 25
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from ..config import settings
from .model import PATTERN_CLASSES, build_model

log = logging.getLogger("train_v2")


def _split(X_full, X_early, y, val_frac=0.15, seed=0):
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(y))
    n_val = int(len(y) * val_frac)
    val_idx = perm[:n_val]
    train_idx = perm[n_val:]
    return (
        (X_full[train_idx], X_early[train_idx], y[train_idx]),
        (X_full[val_idx], X_early[val_idx], y[val_idx]),
    )


def _per_class_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    out: dict[str, float] = {}
    for i, name in enumerate(PATTERN_CLASSES):
        mask = y_true == i
        if mask.sum() == 0:
            out[name] = float("nan")
            continue
        out[name] = float((y_pred[mask] == i).mean())
    return out


def _confusion(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    n = len(PATTERN_CLASSES)
    cm = np.zeros((n, n), dtype=np.int64)
    for t, p in zip(y_true.tolist(), y_pred.tolist()):
        cm[t, p] += 1
    return cm


def _print_confusion(cm: np.ndarray) -> None:
    n = len(PATTERN_CLASSES)
    name_w = max(len(c) for c in PATTERN_CLASSES) + 2
    print("Confusion matrix (rows=true, cols=pred):")
    print(" " * name_w + "  ".join(f"{i:>5}" for i in range(n)))
    for i, name in enumerate(PATTERN_CLASSES):
        row = "  ".join(f"{cm[i, j]:>5}" for j in range(n))
        print(f"{i:>2} {name:<{name_w-3}}{row}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="../data/ml/corpus.npz")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--patience", type=int, default=5,
                    help="Early stopping patience (val accuracy plateau).")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    data = np.load(args.npz)
    X_full, X_early, y = data["X_full"], data["X_early"], data["y"]
    counts = np.bincount(y, minlength=len(PATTERN_CLASSES))
    log.info("class counts: %s", dict(zip(PATTERN_CLASSES, counts.tolist())))

    (Xf_tr, Xe_tr, y_tr), (Xf_val, Xe_val, y_val) = _split(X_full, X_early, y)
    log.info("train=%d val=%d", len(y_tr), len(y_val))

    import torch
    from torch.utils.data import DataLoader, TensorDataset

    # Inverse-frequency class weights so rare classes aren't ignored.
    # Cap at 5x to keep gradient magnitudes sane when one class is missing
    # or extremely rare — uncapped weights collapse training.
    raw = counts.sum() / np.maximum(counts, 1)
    weights = np.clip(raw / raw.mean(), 0.5, 5.0).astype(np.float32)
    log.info("class weights: %s", dict(zip(PATTERN_CLASSES, weights.round(3).tolist())))

    train_ds = TensorDataset(
        torch.from_numpy(Xf_tr), torch.from_numpy(Xe_tr), torch.from_numpy(y_tr)
    )
    val_ds = TensorDataset(
        torch.from_numpy(Xf_val), torch.from_numpy(Xe_val), torch.from_numpy(y_val)
    )
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=args.batch, shuffle=False)

    model = build_model()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    loss_fn = torch.nn.CrossEntropyLoss(
        weight=torch.from_numpy(weights).to(device),
        label_smoothing=0.05,
    )

    out_path = Path(settings.model_path)
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parent.parent.parent / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    best_val_acc = -1.0
    bad_epochs = 0

    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        n_seen = 0
        for xb, xe, yb in train_dl:
            xb, xe, yb = xb.to(device), xe.to(device), yb.to(device)
            opt.zero_grad()
            pat_logits, _ = model(xb)
            _, early_logits = model(xe)
            loss = 0.6 * loss_fn(pat_logits, yb) + 0.4 * loss_fn(early_logits, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            opt.step()
            train_loss += loss.item() * len(yb)
            n_seen += len(yb)
        sched.step()
        train_loss /= max(1, n_seen)

        model.eval()
        all_pred, all_true = [], []
        val_loss = 0.0
        n_seen = 0
        with torch.no_grad():
            for xb, _, yb in val_dl:
                xb, yb = xb.to(device), yb.to(device)
                pat_logits, _ = model(xb)
                val_loss += loss_fn(pat_logits, yb).item() * len(yb)
                n_seen += len(yb)
                all_pred.append(pat_logits.argmax(dim=-1).cpu().numpy())
                all_true.append(yb.cpu().numpy())
        val_loss /= max(1, n_seen)
        y_pred = np.concatenate(all_pred)
        y_true = np.concatenate(all_true)
        val_acc = float((y_pred == y_true).mean())

        log.info(
            "epoch %2d  train_loss=%.4f  val_loss=%.4f  val_acc=%.3f",
            epoch, train_loss, val_loss, val_acc,
        )

        if val_acc > best_val_acc + 1e-4:
            best_val_acc = val_acc
            bad_epochs = 0
            torch.save(model.state_dict(), out_path)
            log.info("  saved %s (val_acc=%.3f)", out_path, val_acc)
        else:
            bad_epochs += 1
            if bad_epochs >= args.patience:
                log.info("early stop after %d epochs without improvement", bad_epochs)
                break

    # Final report on the best checkpoint.
    model.load_state_dict(torch.load(out_path, map_location=device))
    model.eval()
    all_pred, all_true = [], []
    with torch.no_grad():
        for xb, _, yb in val_dl:
            xb = xb.to(device)
            pat_logits, _ = model(xb)
            all_pred.append(pat_logits.argmax(dim=-1).cpu().numpy())
            all_true.append(yb.numpy())
    y_pred = np.concatenate(all_pred)
    y_true = np.concatenate(all_true)
    log.info("--- Final per-class accuracy (best checkpoint) ---")
    for name, acc in _per_class_accuracy(y_true, y_pred).items():
        log.info("  %-30s %.2f", name, acc)
    _print_confusion(_confusion(y_true, y_pred))


if __name__ == "__main__":
    main()
