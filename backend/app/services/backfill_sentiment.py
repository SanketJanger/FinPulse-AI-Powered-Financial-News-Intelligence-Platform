"""
One-off backfill: run the current processor over articles that have no
sentiment yet and update them in place.

Used when rolling out V2 so the rows already in Postgres (written by the
v1 pass-through consumer) get scored without having to re-ingest them.

    PROCESSOR_VERSION=v2 python -m app.services.backfill_sentiment [--limit N] [--batch N]
"""
import argparse
import asyncio

from sqlalchemy import select

from app.config import settings
from app.database import async_session, engine
from app.models.article import RawArticle
from app.models.database import ArticleORM
from app.processors import get_processor


async def backfill(limit: int | None, batch: int) -> None:
    processor = get_processor(settings.processor_version)
    if processor.version == "v1":
        print("PROCESSOR_VERSION=v1 has nothing to backfill. Set it to v2.")
        return

    print(f"Loading processor '{processor.version}' ...")
    await processor.startup()

    scanned = updated = 0
    while True:
        async with async_session() as session:
            rows = (
                await session.scalars(
                    select(ArticleORM)
                    .where(ArticleORM.processed_at.is_(None))
                    .order_by(ArticleORM.fetched_at.desc())
                    .limit(batch)
                )
            ).all()

            if not rows:
                break

            for row in rows:
                scanned += 1
                raw = RawArticle(
                    id=row.id,
                    title=row.title,
                    content=row.content,
                    description=row.description,
                    url=row.url,
                    source=row.source,
                    author=row.author,
                    published_at=row.published_at,
                    fetched_at=row.fetched_at,
                )
                enr = await processor.process(raw)
                if enr.sentiment is None:
                    continue
                row.sentiment = enr.sentiment
                row.confidence = enr.confidence
                row.impact_score = enr.impact_score
                row.processed_at = enr.processed_at
                updated += 1
                print(f"  [{enr.sentiment:<7} c={enr.confidence:.3f} impact={enr.impact_score}] {row.title[:70]}")

            await session.commit()

        if limit is not None and scanned >= limit:
            break

    await processor.shutdown()
    await engine.dispose()
    print(f"\nDone. scanned={scanned} updated={updated}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="stop after N articles")
    ap.add_argument("--batch", type=int, default=50, help="rows per DB round-trip")
    args = ap.parse_args()
    asyncio.run(backfill(args.limit, args.batch))


if __name__ == "__main__":
    main()
