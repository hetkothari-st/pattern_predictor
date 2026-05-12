"""Small 1D-CNN with two heads: pattern head + early-warning head.

Designed for CPU inference under 50ms on a 120-bar window.
"""
from __future__ import annotations

from typing import Sequence

try:
    import torch
    from torch import nn
except ImportError:  # pragma: no cover
    torch = None  # type: ignore
    nn = None  # type: ignore


PATTERN_CLASSES: list[str] = [
    "none",
    "head_and_shoulders",
    "inverse_head_and_shoulders",
    "double_top",
    "double_bottom",
    "ascending_triangle",
    "descending_triangle",
    "symmetric_triangle",
    "rising_wedge",
    "falling_wedge",
    "bull_flag",
    "bear_flag",
    "cup_with_handle",
]


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError("PyTorch not installed. `pip install -e '.[ml]'`")


def build_model(in_channels: int = 5, n_classes: int = len(PATTERN_CLASSES)) -> "nn.Module":
    _require_torch()

    class CNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.backbone = nn.Sequential(
                nn.Conv1d(in_channels, 32, kernel_size=7, padding=3),
                nn.BatchNorm1d(32),
                nn.ReLU(),
                nn.Conv1d(32, 64, kernel_size=5, padding=2),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.MaxPool1d(2),
                nn.Dropout(0.2),
                nn.Conv1d(64, 128, kernel_size=5, padding=2),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.MaxPool1d(2),
                nn.Dropout(0.3),
                nn.Conv1d(128, 128, kernel_size=3, padding=1),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
                nn.Dropout(0.4),
            )
            self.pattern_head = nn.Linear(128, n_classes)
            self.early_head = nn.Linear(128, n_classes)

        def forward(self, x):  # type: ignore[override]
            feats = self.backbone(x)
            return self.pattern_head(feats), self.early_head(feats)

    return CNN()


def softmax_probs(logits: "torch.Tensor", classes: Sequence[str] = PATTERN_CLASSES) -> dict[str, float]:
    _require_torch()
    probs = torch.softmax(logits, dim=-1).squeeze(0).tolist()
    return {classes[i]: float(p) for i, p in enumerate(probs)}
