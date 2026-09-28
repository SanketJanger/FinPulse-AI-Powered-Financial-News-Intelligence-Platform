"""
Phase 8 — model evaluation harness.

Compares VADER vs FinBERT vs Groq gpt-oss-120b on financial-news sentiment
against a GPT-4o-mini reference, and evaluates the MiniLM+ChromaDB
retrieval pipeline (Precision@k, MRR).

    python -m scripts.evaluation                 # full run, n=200
    python -m scripts.evaluation --n 120
    python -m scripts.evaluation --reuse-labels  # keep test_set.csv, redo the rest
    python -m scripts.evaluation --reuse-labels --reuse-predictions --skip-rag

All artefacts land in backend/eval_output/. Long steps checkpoint to CSV,
so a re-run with the --reuse-* flags resumes instead of re-spending API calls.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

from app.config import settings
from scripts.eval.charts import (
    confusion_grid,
    latency_bar,
    model_comparison_bar,
    per_class_f1,
)
from scripts.eval.classifiers import (
    FinbertClassifier,
    GroqLLMClassifier,
    VaderClassifier,
)
from scripts.eval.dataset import EvalArticle, build_test_set
from scripts.eval.labeler import OpenAILabeler
from scripts.eval.metrics import label_distribution, score_model
from scripts.eval.rag_eval import build_eval_index, run_rag_eval
from scripts.eval.report import build_report

OUT = Path(__file__).resolve().parent.parent / "eval_output"
FIG = OUT / "figures"
TEST_SET = OUT / "test_set.csv"
PREDS = OUT / "predictions.csv"
METRICS = OUT / "metrics.json"
RAG_JUDGE = OUT / "rag_judgements.csv"
RAG_METRICS = OUT / "rag_metrics.json"
REPORT = OUT / "EVALUATION_REPORT.md"


def _need_key(name: str, value: str) -> None:
    if not value:
        raise SystemExit(f"{name} is not set in backend/.env — required for this run.")


# ---------------------------------------------------------------- step 1: labels
def build_labelled_set(n: int) -> list[dict]:
    _need_key("OPENAI_API_KEY", settings.openai_api_key)
    print(f"[1/5] Sampling {n} articles and labelling with {settings.eval_label_model} ...")
    articles = build_test_set(n)
    labeler = OpenAILabeler(settings.openai_api_key, settings.eval_label_model)

    rows: list[dict] = []
    with TEST_SET.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "article_id", "title", "content", "ground_truth_sentiment",
                "gt_confidence", "gt_stable", "gt_rationale", "source", "url",
            ],
        )
        w.writeheader()
        for i, a in enumerate(articles, 1):
            res = labeler.label(a.model_input())
            row = {
                "article_id": a.article_id,
                "title": a.title,
                "content": a.text,
                "ground_truth_sentiment": res.label,
                "gt_confidence": round(res.confidence, 3),
                "gt_stable": int(res.stable),
                "gt_rationale": res.rationale,
                "source": a.source,
                "url": a.url,
            }
            rows.append(row)
            w.writerow(row)
            f.flush()
            if i % 20 == 0 or i == len(articles):
                print(f"    labelled {i}/{len(articles)}")
    return rows


def load_labelled_set() -> list[dict]:
    with TEST_SET.open() as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------- step 2: classifier preds
def run_classifiers(rows: list[dict], resume: bool) -> list[dict]:
    _need_key("GROQ_API_KEY", settings.groq_api_key)
    print("[2/5] Running VADER / FinBERT / Groq classifiers ...")

    done: dict[str, dict] = {}
    if resume and PREDS.exists():
        with PREDS.open() as f:
            for r in csv.DictReader(f):
                done[r["article_id"]] = r
        print(f"    resuming — {len(done)} rows already predicted")

    vader = VaderClassifier()
    finbert = FinbertClassifier()
    groq = GroqLLMClassifier(settings.groq_api_key, settings.eval_groq_model, min_interval_s=5.0)

    fields = [
        "article_id", "ground_truth", "gt_stable",
        "vader", "vader_ms", "finbert", "finbert_ms", "groq_llm", "groq_ms",
    ]
    out_rows: list[dict] = []
    mode = "a" if done else "w"
    with PREDS.open(mode, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not done:
            w.writeheader()
        for i, src in enumerate(rows, 1):
            aid = src["article_id"]
            if aid in done:
                out_rows.append(done[aid])
                continue
            text = f"{src['title']}\n\n{src['content']}".strip()
            v_lab, v_dt = vader.predict(text)
            f_lab, f_dt = finbert.predict(text)
            g_lab, g_dt = groq.predict(text[:4000])
            row = {
                "article_id": aid,
                "ground_truth": src["ground_truth_sentiment"],
                "gt_stable": src.get("gt_stable", ""),
                "vader": v_lab, "vader_ms": round(v_dt * 1000, 3),
                "finbert": f_lab, "finbert_ms": round(f_dt * 1000, 3),
                "groq_llm": g_lab, "groq_ms": round(g_dt * 1000, 1),
            }
            out_rows.append(row)
            w.writerow(row)
            f.flush()
            if i % 10 == 0 or i == len(rows):
                print(f"    {i}/{len(rows)}  (groq {g_dt:.1f}s)")
    return out_rows


# ---------------------------------------------------------------- step 3: metrics
def compute_metrics(pred_rows: list[dict]) -> tuple[list, list, dict]:
    models = [
        ("VADER", "vader", "vader_ms"),
        ("FinBERT", "finbert", "finbert_ms"),
        (settings.eval_groq_model, "groq_llm", "groq_ms"),
    ]
    y_true = [r["ground_truth"] for r in pred_rows]
    stable_mask = [str(r.get("gt_stable", "")) == "1" for r in pred_rows]

    full, stable = [], []
    for name, col, lat_col in models:
        y_pred = [r[col] for r in pred_rows]
        lat_s = [float(r[lat_col]) / 1000 for r in pred_rows]
        full.append(score_model(name, y_true, y_pred, lat_s))

        yt = [t for t, m in zip(y_true, stable_mask) if m]
        yp = [p for p, m in zip(y_pred, stable_mask) if m]
        ls = [x for x, m in zip(lat_s, stable_mask) if m]
        if yt:
            stable.append(score_model(name, yt, yp, ls))

    meta = {
        "n": len(pred_rows),
        "n_stable": sum(stable_mask),
        "gt_distribution": label_distribution(y_true),
    }
    return full, stable, meta


# ------------------------------------------------------------------- step 4: RAG
def run_rag(rows: list[dict]) -> object:
    _need_key("OPENAI_API_KEY", settings.openai_api_key)
    print("[4/5] Building eval vector index and running retrieval eval ...")
    from app.analysis.embeddings import Embedder

    embedder = Embedder(settings.embedding_model)
    embedder.load()

    arts = [
        EvalArticle(
            article_id=r["article_id"], title=r["title"], text=r["content"],
            source=r["source"], url=r["url"], published_at=None,
        )
        for r in rows
    ]
    col = build_eval_index(arts, embedder, settings.chroma_host, settings.chroma_port)
    report, judge_rows = run_rag_eval(
        col, embedder, settings.openai_api_key, settings.eval_label_model, k=10
    )

    with RAG_JUDGE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(judge_rows[0].keys()))
        w.writeheader()
        w.writerows(judge_rows)
    RAG_METRICS.write_text(
        json.dumps(
            {
                "map_p_at_5": report.map_p_at_5,
                "map_p_at_10": report.map_p_at_10,
                "mrr": report.mrr,
                "mean_query_latency_ms": report.mean_query_latency_ms,
                "per_query": [
                    {
                        "query": q.query, "p_at_5": q.p_at_5, "p_at_10": q.p_at_10,
                        "reciprocal_rank": q.reciprocal_rank, "relevant_flags": q.relevant_flags,
                    }
                    for q in report.per_query
                ],
            },
            indent=2,
        )
    )
    return report


# ------------------------------------------------------------------------ driver
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--reuse-labels", action="store_true")
    ap.add_argument("--reuse-predictions", action="store_true")
    ap.add_argument("--reuse-rag", action="store_true", help="load rag_metrics.json instead of re-running retrieval eval")
    ap.add_argument("--skip-rag", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    timings: dict[str, float] = {}

    # 1. labelled test set
    t = time.time()
    if args.reuse_labels and TEST_SET.exists():
        print(f"[1/5] Reusing {TEST_SET.name}")
        rows = load_labelled_set()
    else:
        rows = build_labelled_set(args.n)
    timings["label"] = time.time() - t

    # 2. classifier predictions
    t = time.time()
    pred_rows = run_classifiers(rows, resume=args.reuse_predictions)
    timings["classify"] = time.time() - t

    # 3. metrics
    print("[3/5] Scoring ...")
    full, stable, meta = compute_metrics(pred_rows)
    METRICS.write_text(
        json.dumps(
            {
                "meta": meta,
                "full": [s.__dict__ for s in full],
                "stable_subset": [s.__dict__ for s in stable],
            },
            indent=2,
        )
    )
    for s in full:
        print(f"    {s.model:<22} acc {s.accuracy:.3f}  macroF1 {s.macro_f1:.3f}  κ {s.kappa:.3f}")

    # 4. RAG
    from scripts.eval.rag_eval import QueryResult, RagReport

    if args.skip_rag:
        print("[4/5] Skipping RAG eval (--skip-rag)")
        rag = RagReport(0, 0.0, 0.0, 0.0, 0.0, [], 0.0)
    elif args.reuse_rag and RAG_METRICS.exists():
        print(f"[4/5] Reusing {RAG_METRICS.name}")
        d = json.loads(RAG_METRICS.read_text())
        pq = [
            QueryResult(
                query=q["query"], n_hits=len(q["relevant_flags"]),
                p_at_5=q["p_at_5"], p_at_10=q["p_at_10"],
                reciprocal_rank=q["reciprocal_rank"], relevant_flags=q["relevant_flags"],
            )
            for q in d["per_query"]
        ]
        rag = RagReport(
            n_queries=len(pq), map_p_at_5=d["map_p_at_5"], map_p_at_10=d["map_p_at_10"],
            mrr=d["mrr"], mean_hits=sum(x.n_hits for x in pq) / max(len(pq), 1),
            per_query=pq, mean_query_latency_ms=d["mean_query_latency_ms"],
        )
    else:
        t = time.time()
        rag = run_rag(rows)
        timings["rag"] = time.time() - t
        print(f"    P@5 {rag.map_p_at_5:.3f}  P@10 {rag.map_p_at_10:.3f}  MRR {rag.mrr:.3f}")

    # 5. figures + report
    print("[5/5] Rendering figures and report ...")
    figures = {
        "confusion": str(confusion_grid(full, FIG / "confusion_matrices.png").relative_to(OUT)),
        "comparison": str(model_comparison_bar(full, FIG / "model_comparison.png").relative_to(OUT)),
        "per_class": str(per_class_f1(full, FIG / "per_class_f1.png").relative_to(OUT)),
        "latency": str(latency_bar(full, FIG / "latency.png").relative_to(OUT)),
    }

    # temp-0 vs temp-0.5 agreement is captured per-row in gt_stable; derive a
    # single κ for the two passes from the observed agreement + label marginals.
    n = len(rows)
    n_stable = sum(1 for r in rows if str(r.get("gt_stable")) == "1")
    kappa_ab = _kappa_from_stability(rows)

    md = build_report(
        n=n,
        n_stable=n_stable,
        gt_dist=meta["gt_distribution"],
        kappa_ab=kappa_ab,
        scores=full,
        scores_stable=stable or None,
        rag=rag,
        rag_judge_model=settings.eval_label_model,
        label_model=settings.eval_label_model,
        groq_model=settings.eval_groq_model,
        figures=figures,
        timings=timings,
    )
    REPORT.write_text(md)
    print(f"\nDone. Report: {REPORT}")
    print(f"Artefacts in: {OUT}/")


def _kappa_from_stability(rows: list[dict]) -> float:
    """Approximate Cohen's κ between the two label passes using the observed
    agreement rate and the temp-0 label marginals (temp-0.5 marginals are
    not stored individually)."""
    n = len(rows)
    if n == 0:
        return 0.0
    po = sum(1 for r in rows if str(r.get("gt_stable")) == "1") / n
    from collections import Counter

    c = Counter(r["ground_truth_sentiment"] for r in rows)
    pe = sum((v / n) ** 2 for v in c.values())
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


if __name__ == "__main__":
    main()
