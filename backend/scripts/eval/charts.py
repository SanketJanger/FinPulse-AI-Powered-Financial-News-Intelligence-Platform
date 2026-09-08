"""
PNG charts for the report. matplotlib + seaborn, 150 dpi, colour-blind-safe
categorical palette (Okabe-Ito). Every chart is also expressible from the
CSVs, so the figures are illustrative, not the source of truth.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from scripts.eval.metrics import CLASSES, ModelScores

# Okabe-Ito — colour-blind safe
MODEL_COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7"]

sns.set_theme(style="whitegrid", context="paper")
plt.rcParams.update({"figure.dpi": 150, "savefig.dpi": 150, "font.size": 10})


def confusion_grid(scores: list[ModelScores], out: Path) -> Path:
    n = len(scores)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 3.8))
    if n == 1:
        axes = [axes]
    for ax, s in zip(axes, scores):
        cm = np.array(s.confusion)
        cm_norm = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
        sns.heatmap(
            cm_norm,
            annot=np.array(
                [[f"{cm[i, j]}\n{cm_norm[i, j]*100:.0f}%" for j in range(3)] for i in range(3)]
            ),
            fmt="",
            cmap="Blues",
            vmin=0,
            vmax=1,
            cbar=False,
            xticklabels=CLASSES,
            yticklabels=CLASSES,
            ax=ax,
            linewidths=0.5,
            linecolor="white",
        )
        ax.set_title(f"{s.model}\nacc {s.accuracy:.2f} · macro-F1 {s.macro_f1:.2f}", fontsize=10)
        ax.set_xlabel("predicted")
        ax.set_ylabel("actual (ground truth)")
    fig.suptitle("Confusion matrices (row-normalised)", y=1.02, fontsize=12)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def model_comparison_bar(scores: list[ModelScores], out: Path) -> Path:
    metrics = ["accuracy", "macro_f1", "weighted_f1", "kappa"]
    labels = ["Accuracy", "Macro F1", "Weighted F1", "Cohen's κ"]
    x = np.arange(len(metrics))
    w = 0.8 / len(scores)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    for i, s in enumerate(scores):
        vals = [getattr(s, m) for m in metrics]
        bars = ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=s.model, color=MODEL_COLORS[i])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    ax.set_title("Sentiment classification — model comparison vs GPT-4o-mini ground truth")
    ax.legend(frameon=False, ncol=len(scores), loc="upper center", bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def per_class_f1(scores: list[ModelScores], out: Path) -> Path:
    x = np.arange(len(CLASSES))
    w = 0.8 / len(scores)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for i, s in enumerate(scores):
        vals = [s.per_class[c]["f1"] for c in CLASSES]
        bars = ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=s.model, color=MODEL_COLORS[i])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.capitalize() for c in CLASSES])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1")
    ax.set_title("Per-class F1")
    ax.legend(frameon=False, ncol=len(scores), loc="upper center", bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def latency_bar(scores: list[ModelScores], out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    names = [s.model for s in scores]
    means = [s.mean_latency_ms for s in scores]
    p95 = [s.p95_latency_ms for s in scores]
    x = np.arange(len(names))
    ax.bar(x - 0.19, means, 0.36, label="mean", color="#0072B2")
    ax.bar(x + 0.19, p95, 0.36, label="p95", color="#E69F00")
    for i, (m, p) in enumerate(zip(means, p95)):
        ax.text(i - 0.19, m, f"{m:.1f}", ha="center", va="bottom", fontsize=8)
        ax.text(i + 0.19, p, f"{p:.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_yscale("log")
    ax.set_ylabel("per-article latency (ms, log scale)")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_title("Inference latency per article")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out
