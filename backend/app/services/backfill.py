"""
One-off backfill: run the current processor over articles already in
Postgres and update them in place — no re-ingestion through Kafka.

    # score rows that were never enriched (rolling out V2/V3)
    PROCESSOR_VERSION=v3 python -m app.services.backfill

    # re-run everything (e.g. after changing the impact-score rule)
    PROCESSOR_VERSION=v3 python -m app.services.backfill --all

    #                                        [--limit N] [--batch N]
"""
import argparse
import asyncio

from sqlalchemy import select

from app.config import settings
from app.database import async_session, engine
from app.models.article import RawArticle
from app.models.database import ArticleORM
from app.processors import get_processor

_FIELDS = (
    "sentiment", "confidence", "impact_score", "processed_at",
    "summary", "tickers", "companies", "category", "embedding_id",
)


async def _load_ids(reprocess_all: bool) -> list:
    async with async_session() as session:
        stmt = select(ArticleORM.id).order_by(ArticleORM.fetched_at.desc())
        if not reprocess_all:
            stmt = stmt.where(ArticleORM.processed_at.is_(None))
        return list(await session.scalars(stmt))


async def backfill(reprocess_all: bool, limit: int | None, batch: int) -> None:
    processor = get_processor(settings.processor_version)
    if processor.version == "v1":
        print("PROCESSOR_VERSION=v1 has nothing to backfill. Set it to v2 or v3.")
        return

    ids = await _load_ids(reprocess_all)
    if limit is not None:
        ids = ids[:limit]
    print(f"Processor '{processor.version}' — {len(ids)} article(s) to (re)process.")
    if not ids:
        return

    await processor.startup()

    done = updated = 0
    for start in range(0, len(ids), batch):
        chunk = ids[start : start + batch]
        async with async_session() as session:
            rows = (
                await session.scalars(select(ArticleORM).where(ArticleORM.id.in_(chunk)))
            ).all()
            for row in rows:
                done += 1
                raw = RawArticle(
                    id=row.id, title=row.title, content=row.content,
                    description=row.description, url=row.url, source=row.source,
                    author=row.author, published_at=row.published_at,
                    fetched_at=row.fetched_at,
                )
                enr = await processor.process(raw)
                for f in _FIELDS:
                    setattr(row, f, getattr(enr, f))
                if enr.sentiment is not None:
                    updated += 1
                print(
                    f"  [{done}/{len(ids)}] {enr.sentiment or '?':<7} "
                    f"impact={enr.impact_score} cat={enr.category or '-'} "
                    f"tick={','.join(enr.tickers or []) or '-'} "
                    f"sum={'y' if enr.summary else 'n'} | {row.title[:55]}"
                )
            await session.commit()

    await processor.shutdown()
    await engine.dispose()
    print(f"\nDone. processed={done} enriched={updated}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="reprocess every row, not just un-enriched ones")
    ap.add_argument("--limit", type=int, default=None, help="stop after N articles")
    ap.add_argument("--batch", type=int, default=50, help="rows per DB round-trip")
    args = ap.parse_args()
    asyncio.run(backfill(args.all, args.limit, args.batch))


if __name__ == "__main__":
    main()
