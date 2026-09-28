"""
Classification metrics on top of scikit-learn.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sklearn.metrics import (
    accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

CLASSES = ["bullish", "bearish", "neutral"]


@dataclass
class ModelScores:
    model: str
    n: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    weighted_f1: float
    kappa: float  # vs ground truth (chance-corrected agreement)
    per_class: dict[str, dict[str, float]]  # class -> {precision,recall,f1,support}
    confusion: list[list[int]]  # rows = true CLASSES, cols = pred CLASSES
    mean_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    total_time_s: float


def _pctl(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    i = min(len(s) - 1, int(round(q * (len(s) - 1))))
    return s[i]


def score_model(
    model: str,
    y_true: list[str],
    y_pred: list[str],
    latencies_s: list[float],
) -> ModelScores:
    acc = accuracy_score(y_true, y_pred)
    p, r, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, zero_division=0
    )
    mp, mr, mf1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, average="macro", zero_division=0
    )
    _, _, wf1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, average="weighted", zero_division=0
    )
    _, _, _, support = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES).tolist()
    lat_ms = [x * 1000 for x in latencies_s]

    return ModelScores(
        model=model,
        n=len(y_true),
        accuracy=acc,
        macro_precision=mp,
        macro_recall=mr,
        macro_f1=mf1,
        weighted_f1=wf1,
        kappa=cohen_kappa_score(y_true, y_pred, labels=CLASSES),
        per_class={
            c: {
                "precision": p[i],
                "recall": r[i],
                "f1": f1[i],
                "support": int(support[i]),
            }
            for i, c in enumerate(CLASSES)
        },
        confusion=cm,
        mean_latency_ms=sum(lat_ms) / len(lat_ms) if lat_ms else 0.0,
        median_latency_ms=_pctl(lat_ms, 0.5),
        p95_latency_ms=_pctl(lat_ms, 0.95),
        total_time_s=sum(latencies_s),
    )


def label_distribution(labels: list[str]) -> dict[str, int]:
    return {c: labels.count(c) for c in CLASSES}
