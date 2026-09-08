"""
Assemble the Markdown evaluation report.
"""
from __future__ import annotations

from datetime import UTC, datetime

from scripts.eval.metrics import CLASSES, ModelScores, label_distribution
from scripts.eval.rag_eval import RagReport


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def build_report(
    *,
    n: int,
    n_stable: int,
    gt_dist: dict[str, int],
    kappa_ab: float,
    scores: list[ModelScores],
    scores_stable: list[ModelScores] | None,
    rag: RagReport,
    rag_judge_model: str,
    label_model: str,
    groq_model: str,
    figures: dict[str, str],
    timings: dict[str, float],
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = []
    A = L.append

    A(f"# FinPulse — Model Evaluation Report\n")
    A(f"_Generated {now}_\n")
    A(
        "This report compares three sentiment-classification approaches — a lexicon "
        "baseline (**VADER**), a domain-tuned transformer (**FinBERT**, "
        "`ProsusAI/finbert`), and a large instruction-tuned LLM "
        f"(**{groq_model}** via Groq) — on financial news headlines, and evaluates the "
        "platform's semantic-search retrieval. All predictions, judgements and "
        "intermediate artefacts are written to CSV for reproducibility.\n"
    )

    # ---------------------------------------------------------------- methodology
    A("## 1. Methodology\n")
    A("### 1.1 Test set\n")
    A(
        f"- **{n} articles** sampled from the platform's Postgres store "
        f"({gt_dist and sum(gt_dist.values())} labelled), stratified by source "
        "with a per-source cap and a fixed RNG seed (`scripts/eval/dataset.py`).\n"
        "- Each item is the article **headline plus available body text** — the same "
        "input the production pipeline scores.\n"
        f"- Ground-truth label distribution: "
        + ", ".join(f"**{k}** {v}" for k, v in gt_dist.items())
        + ".\n"
    )
    A("### 1.2 Ground truth\n")
    A(
        f"- Labelled by **OpenAI `{label_model}`**, which is *not* one of the systems "
        "under test — this keeps the reference labels independent of VADER, FinBERT "
        "and the Groq LLM.\n"
        "- A fixed 3-class **market-impact rubric** (bullish / bearish / neutral) is "
        "used; see `scripts/eval/labeler.py`.\n"
        "- **Self-consistency check:** every article is labelled twice — once at "
        "temperature 0, once at 0.5. The final label is the temperature-0 pass; "
        f"the two passes agree on **{n_stable}/{n}** items ({_pct(n_stable / n)}), "
        f"a chance-corrected agreement of κ ≈ **{kappa_ab:.2f}** (approximated from "
        "the agreement rate and the label marginals — the second pass's individual "
        "labels are not retained). The per-item agreement is recorded as `gt_stable`; "
        "metrics are reported on the full set and on the stable subset.\n"
    )
    A("### 1.3 Systems under test\n")
    A(
        _table(
            ["System", "Type", "Decision rule"],
            [
                ["VADER", "lexicon + heuristics", "compound > 0.05 → bullish; < −0.05 → bearish; else neutral"],
                ["FinBERT", "BERT fine-tuned on financial text", "arg-max of {positive, negative, neutral} → {bullish, bearish, neutral}"],
                [f"{groq_model}", "instruction-tuned LLM, zero-shot", "same rubric as ground truth, `reasoning_effort=low`, temp 0"],
            ],
        )
    )
    A("")
    A("### 1.4 Retrieval evaluation\n")
    A(
        f"- **20 topical queries** run against a dedicated ChromaDB collection built "
        f"from the {n}-article test set (MiniLM `all-MiniLM-L6-v2`, cosine).\n"
        f"- Each (query, hit) pair in the top-10 is judged relevant / not by "
        f"**`{rag_judge_model}`** (LLM-as-judge); see `scripts/eval/rag_eval.py`.\n"
        "- Metrics: **Precision@5**, **Precision@10**, **MRR**, macro-averaged over the 20 queries.\n"
    )

    # ---------------------------------------------------------------- results
    A("## 2. Sentiment classification results\n")
    A("### 2.1 Headline metrics (full test set, n = %d)\n" % n)
    rows = []
    for s in scores:
        rows.append(
            [
                s.model,
                _pct(s.accuracy),
                _pct(s.macro_precision),
                _pct(s.macro_recall),
                f"**{_pct(s.macro_f1)}**",
                _pct(s.weighted_f1),
                f"{s.kappa:.3f}",
            ]
        )
    A(_table(["Model", "Accuracy", "Macro P", "Macro R", "Macro F1", "Weighted F1", "κ vs GT"], rows))
    A("")
    A(f"![model comparison]({figures['comparison']})\n")

    if scores_stable:
        A("### 2.2 Headline metrics (stable-label subset, n = %d)\n" % n_stable)
        rows = []
        for s in scores_stable:
            rows.append(
                [s.model, _pct(s.accuracy), f"**{_pct(s.macro_f1)}**", _pct(s.weighted_f1), f"{s.kappa:.3f}"]
            )
        A(_table(["Model", "Accuracy", "Macro F1", "Weighted F1", "κ vs GT"], rows))
        A("")

    A("### 2.3 Per-class F1 (full set)\n")
    rows = []
    for s in scores:
        rows.append(
            [s.model] + [f"{s.per_class[c]['f1']:.2f} (n={s.per_class[c]['support']})" for c in CLASSES]
        )
    A(_table(["Model"] + [c.capitalize() for c in CLASSES], rows))
    A("")
    A(f"![per-class F1]({figures['per_class']})\n")

    A("### 2.4 Confusion matrices\n")
    A(f"![confusion matrices]({figures['confusion']})\n")
    for s in scores:
        A(f"**{s.model}** — rows = actual, columns = predicted:\n")
        header = ["actual ↓ / pred →"] + CLASSES
        rows = [[CLASSES[i]] + [str(v) for v in s.confusion[i]] for i in range(3)]
        A(_table(header, rows))
        A("")

    # ---------------------------------------------------------------- latency
    A("## 3. Inference cost\n")
    A(
        _table(
            ["Model", "Mean / article", "Median", "p95", "Total (n=%d)" % n, "Notes"],
            [
                [
                    s.model,
                    f"{s.mean_latency_ms:.1f} ms",
                    f"{s.median_latency_ms:.1f} ms",
                    f"{s.p95_latency_ms:.1f} ms",
                    f"{s.total_time_s:.1f} s",
                    "local CPU" if s.model in ("VADER", "FinBERT") else "network / API latency",
                ]
                for s in scores
            ],
        )
    )
    A("")
    A(f"![latency]({figures['latency']})\n")
    A(
        "> VADER and FinBERT run locally (CPU); the Groq figure is end-to-end API "
        "latency including network and queueing, not model compute, and is rate-limited "
        "on the free tier.\n"
    )

    # ---------------------------------------------------------------- RAG
    A("## 4. Semantic-search retrieval\n")
    A(
        _table(
            ["Metric", "Value"],
            [
                ["Queries", str(rag.n_queries)],
                ["Mean hits / query", f"{rag.mean_hits:.1f}"],
                ["**Precision@5**", f"**{rag.map_p_at_5:.3f}**"],
                ["**Precision@10**", f"**{rag.map_p_at_10:.3f}**"],
                ["**MRR**", f"**{rag.mrr:.3f}**"],
                ["Mean query latency", f"{rag.mean_query_latency_ms:.1f} ms"],
            ],
        )
    )
    A("")
    A("Per-query:\n")
    rows = [
        [q.query[:52], f"{q.p_at_5:.2f}", f"{q.p_at_10:.2f}", f"{q.reciprocal_rank:.2f}"]
        for q in rag.per_query
    ]
    A(_table(["Query", "P@5", "P@10", "RR"], rows))
    A("")

    # ---------------------------------------------------------------- discussion
    A("## 5. Discussion\n")
    best = max(scores, key=lambda s: s.macro_f1)
    worst = min(scores, key=lambda s: s.macro_f1)
    A(
        f"- **{best.model}** has the highest macro-F1 ({_pct(best.macro_f1)}); "
        f"**{worst.model}** the lowest ({_pct(worst.macro_f1)}).\n"
        "- FinBERT vs VADER isolates the value of financial-domain fine-tuning over a "
        "general-purpose lexicon on the same headlines.\n"
        "- The LLM vs FinBERT gap quantifies what a large zero-shot model buys over a "
        "small specialised one, against its per-item latency and cost.\n"
        "- Per-class F1 exposes the usual failure mode: **neutral** is the hardest "
        "class, and lexicon methods over-predict it.\n"
    )

    A("## 6. Threats to validity\n")
    A(
        "- **Model-assisted ground truth.** Labels come from a single LLM annotator "
        f"(`{label_model}`), not human annotators. The temp-0 / temp-0.5 agreement "
        f"(κ ≈ {kappa_ab:.2f}) measures the labeller's *self-consistency*, not its "
        "*correctness*, and is no substitute for multi-rater human adjudication. "
        "Results on the stable subset (§2.2) mitigate but do not remove this.\n"
        "- **Shared rubric.** The Groq LLM classifier and the ground-truth labeller use "
        "the *same* rubric text, which may advantage the LLM relative to VADER/FinBERT. "
        "The rubric encodes a market-impact definition of sentiment that FinBERT was not "
        "trained against.\n"
        "- **Corpus skew.** Articles are recent financial news, source-skewed toward a "
        "few outlets; headline-dominant (many RSS items lack body text).\n"
        "- **LLM-as-judge for retrieval.** Relevance judgements share the judge model "
        "family with the labeller; no human qrels.\n"
        "- **API latency ≠ compute.** Groq timings are not comparable to local CPU "
        "timings as a measure of model efficiency.\n"
    )

    A("## 7. Artefacts\n")
    A(
        _table(
            ["File", "Contents"],
            [
                ["`test_set.csv`", "article_id, title, content, ground_truth_sentiment, gt_confidence, gt_stable, gt_rationale, source, url"],
                ["`predictions.csv`", "per-article predictions + latencies for all 3 models + ground truth"],
                ["`metrics.json`", "full metric objects (full set + stable subset)"],
                ["`rag_judgements.csv`", "per (query, hit) relevance judgement with similarity"],
                ["`rag_metrics.json`", "P@5 / P@10 / MRR overall and per query"],
                ["`figures/*.png`", "confusion matrices, model comparison, per-class F1, latency"],
            ],
        )
    )
    A("")
    A(
        f"_Run time: dataset+labelling {timings.get('label', 0):.0f}s · "
        f"classifiers {timings.get('classify', 0):.0f}s · "
        f"RAG {timings.get('rag', 0):.0f}s._\n"
    )
    return "\n".join(L)
