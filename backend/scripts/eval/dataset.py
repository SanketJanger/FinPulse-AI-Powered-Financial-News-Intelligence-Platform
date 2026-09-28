"""
Build the labelled test set: sample N diverse articles from Postgres.

Diversity strategy: stratify by source (cap per source so no outlet
dominates), prefer articles that carry some body text, deterministic
shuffle with a fixed seed for reproducibility.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from sqlalchemy import select

from app.database import async_session
from app.models.database import ArticleORM

SEED = 20260908


@dataclass
class EvalArticle:
    article_id: str
    title: str
    text: str  # content if present, else description
    source: str
    url: str
    published_at: str | None

    def model_input(self, limit: int = 2000) -> str:
        body = self.text.strip()
        if body:
            return f"{self.title}\n\n{body}"[:limit]
        return self.title[:limit]


async def _fetch_candidates() -> list[EvalArticle]:
    async with async_session() as s:
        rows = (await s.scalars(select(ArticleORM))).all()
    out: list[EvalArticle] = []
    for r in rows:
        text = (r.content or r.description or "").strip()
        # keep anything with a real headline; body text optional
        if len(r.title.strip()) < 15:
            continue
        out.append(
            EvalArticle(
                article_id=str(r.id),
                title=r.title.strip(),
                text=text,
                source=r.source,
                url=r.url,
                published_at=r.published_at.isoformat() if r.published_at else None,
            )
        )
    return out


def _stratified_sample(cands: list[EvalArticle], n: int, per_source_cap: int) -> list[EvalArticle]:
    rng = random.Random(SEED)
    by_source: dict[str, list[EvalArticle]] = {}
    for a in cands:
        by_source.setdefault(a.source, []).append(a)

    # Prefer articles with body text within each source, then shuffle.
    for lst in by_source.values():
        lst.sort(key=lambda a: (len(a.text) == 0, rng.random()))

    picked: list[EvalArticle] = []
    # round-robin across sources up to the cap
    for depth in range(per_source_cap):
        for src in sorted(by_source):
            if depth < len(by_source[src]):
                picked.append(by_source[src][depth])
        if len(picked) >= n * 1.5:
            break

    rng.shuffle(picked)
    return picked[:n]


def build_test_set(n: int = 200, per_source_cap: int = 22) -> list[EvalArticle]:
    cands = asyncio.run(_fetch_candidates())
    sample = _stratified_sample(cands, n, per_source_cap)
    if len(sample) < n:
        # not enough after the cap — fill from the remainder, still seeded
        rng = random.Random(SEED + 1)
        chosen = {a.article_id for a in sample}
        rest = [a for a in cands if a.article_id not in chosen]
        rng.shuffle(rest)
        sample.extend(rest[: n - len(sample)])
    return sample[:n]
