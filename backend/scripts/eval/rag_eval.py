"""
Retrieval evaluation for the semantic-search pipeline
(MiniLM embeddings + ChromaDB cosine kNN).

Relevance is decided per (query, hit) pair by gpt-4o-mini — the same
independent judge model used for the sentiment ground truth — so the
metric doesn't depend on a hand-built qrels file.

Reports Precision@5, Precision@10 and MRR, macro-averaged over the query
set, plus a per-query breakdown.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from openai import OpenAI

from scripts.eval.dataset import EvalArticle

# 20 queries spanning distinct financial themes.
QUERIES: list[str] = [
    "Federal Reserve interest rate decision and its effect on equities",
    "US inflation data and consumer prices",
    "quarterly earnings beat expectations",
    "company misses earnings and guidance cut",
    "oil prices and energy market volatility",
    "Middle East conflict impact on markets",
    "AI chip demand and semiconductor stocks",
    "big tech layoffs and job cuts",
    "cryptocurrency and bitcoin price moves",
    "US tariffs and trade policy",
    "China economy slowdown and stimulus",
    "Treasury yields and bond market stress",
    "mergers and acquisitions deal activity",
    "regulatory investigation or lawsuit against a company",
    "housing market and mortgage rates",
    "stock market rally and record highs",
    "bank capital and financial system stability",
    "electric vehicle makers and automotive industry",
    "airline industry results and travel demand",
    "gold and safe-haven assets",
]

_JUDGE_SYS = (
    "You judge whether a news article is RELEVANT to a search query for a "
    "financial-news retrieval system. Relevant = the article is substantively "
    "about the query's topic and a user issuing that query would want it in the "
    "results. Tangential mentions are NOT relevant. "
    'Respond as JSON: {"relevant": true|false, "why": "<=20 words"}.'
)

EVAL_COLLECTION = "finpulse_eval"


@dataclass
class QueryResult:
    query: str
    n_hits: int
    p_at_5: float
    p_at_10: float
    reciprocal_rank: float
    relevant_flags: list[int]


@dataclass
class RagReport:
    n_queries: int
    map_p_at_5: float
    map_p_at_10: float
    mrr: float
    mean_hits: float
    per_query: list[QueryResult]
    mean_query_latency_ms: float


def build_eval_index(articles: list[EvalArticle], embedder, chroma_host: str, chroma_port: int):
    """(Re)create a dedicated Chroma collection holding exactly the test set."""
    import chromadb

    client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
    try:
        client.delete_collection(EVAL_COLLECTION)
    except Exception:
        pass
    col = client.create_collection(EVAL_COLLECTION, metadata={"hnsw:space": "cosine"})

    texts = [a.model_input(600) for a in articles]
    vecs = embedder.encode(texts)
    col.add(
        ids=[a.article_id for a in articles],
        embeddings=vecs,
        documents=texts,
        metadatas=[{"source": a.source, "title": a.title} for a in articles],
    )
    return col


def _judge(client: OpenAI, model: str, query: str, doc: str) -> int:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _JUDGE_SYS},
            {"role": "user", "content": f"Query: {query}\n\nArticle:\n{doc[:1200]}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=60,
    )
    try:
        return 1 if json.loads(resp.choices[0].message.content).get("relevant") else 0
    except Exception:
        return 0


def run_rag_eval(
    col,
    embedder,
    openai_key: str,
    judge_model: str,
    k: int = 10,
) -> tuple[RagReport, list[dict]]:
    client = OpenAI(api_key=openai_key)
    per_query: list[QueryResult] = []
    judgement_rows: list[dict] = []
    latencies: list[float] = []

    for q in QUERIES:
        qvec = embedder.encode([q])[0]
        t0 = time.perf_counter()
        res = col.query(query_embeddings=[qvec], n_results=k)
        latencies.append((time.perf_counter() - t0) * 1000)

        ids = res["ids"][0]
        docs = res["documents"][0]
        dists = res["distances"][0]
        flags: list[int] = []
        for rank, (aid, doc, dist) in enumerate(zip(ids, docs, dists), start=1):
            rel = _judge(client, judge_model, q, doc)
            flags.append(rel)
            judgement_rows.append(
                {
                    "query": q,
                    "rank": rank,
                    "article_id": aid,
                    "similarity": round(1 - dist, 4),
                    "relevant": rel,
                    "title": doc.split("\n", 1)[0][:120],
                }
            )

        first_rel = next((i for i, f in enumerate(flags, 1) if f), None)
        per_query.append(
            QueryResult(
                query=q,
                n_hits=len(flags),
                p_at_5=sum(flags[:5]) / 5,
                p_at_10=sum(flags[:10]) / 10,
                reciprocal_rank=(1.0 / first_rel) if first_rel else 0.0,
                relevant_flags=flags,
            )
        )

    nq = len(per_query)
    report = RagReport(
        n_queries=nq,
        map_p_at_5=sum(x.p_at_5 for x in per_query) / nq,
        map_p_at_10=sum(x.p_at_10 for x in per_query) / nq,
        mrr=sum(x.reciprocal_rank for x in per_query) / nq,
        mean_hits=sum(x.n_hits for x in per_query) / nq,
        per_query=per_query,
        mean_query_latency_ms=sum(latencies) / len(latencies),
    )
    return report, judgement_rows
