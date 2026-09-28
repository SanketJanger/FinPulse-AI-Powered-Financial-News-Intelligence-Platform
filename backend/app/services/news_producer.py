"""
Phase 2, step 1: fetch from NewsAPI and validate into RawArticle objects.
No Kafka yet — just prove fetch -> validate works, and see what real data looks like
once it's forced through our Pydantic model.
"""
import time
import calendar
from datetime import UTC, datetime
import httpx
import feedparser
from app.config import settings
from app.models.article import RawArticle
import hashlib
import redis
from confluent_kafka import Producer

def fetch_newsapi_articles(page_size: int = 5) -> list[RawArticle]:
    """Calls NewsAPI's top-headlines endpoint and returns validated RawArticle objects.
    Any article that fails validation is skipped, with a printed warning —
    we never want one bad article to crash the whole fetch."""
    url = "https://newsapi.org/v2/top-headlines"
    params = {"category": "business", "country": "us", "pageSize": page_size}
    headers = {"X-Api-Key": settings.newsapi_key}

    response = httpx.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()  # raises an exception if NewsAPI returned an error status
    data = response.json()

    articles = []
    for raw in data["articles"]:
        try:
            article = RawArticle(
                title=raw["title"],
                description=raw.get("description"),
                content=raw.get("content"),
                url=raw["url"],
                source=raw["source"]["name"],
                author=raw.get("author"),
                published_at=raw.get("publishedAt"),
            )
            articles.append(article)
        except Exception as e:
            print(f"Skipping invalid article ({raw.get('url')}): {e}")

    return articles

RSS_FEEDS = {
    "CNBC RSS": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "CNBC Economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "CNBC Finance": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "MarketWatch Top": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "MarketWatch RealTime": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "MarketWatch Markets": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "Investing.com News": "https://www.investing.com/rss/news.rss",
    "Investing.com Stock": "https://www.investing.com/rss/news_25.rss",
    "Seeking Alpha": "https://seekingalpha.com/market_currents.xml",
    "NYT Business": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "NYT Economy": "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    "Guardian Business": "https://www.theguardian.com/uk/business/rss",
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "Fortune": "https://fortune.com/feed/",
    "Business Insider": "https://markets.businessinsider.com/rss/news",
}
kafka_producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)

def is_duplicate(url: str) -> bool:
    """Checks whether we've already processed this URL within the last 7 days.
    If new, marks it as seen and returns False. If already seen, returns True
    without re-marking it (no need to reset the expiration clock)."""
    key = f"seen:{hashlib.sha256(url.encode()).hexdigest()}"
    if redis_client.exists(key):
        return True
    redis_client.setex(key, 604800, "1")  # 7 days
    return False

def fetch_rss_articles() -> list[RawArticle]:
    """Fetches from each configured RSS feed and returns validated RawArticle objects.
    Same defensive pattern as NewsAPI: one bad entry gets skipped and logged,
    never crashes the whole fetch."""
    articles = []

    for source_name, feed_url in RSS_FEEDS.items():
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            try:
                article = RawArticle(
                    title=entry.title,
                    description=getattr(entry, "summary", None),
                    url=entry.link,
                    source=source_name,
                    published_at=_parse_rss_timestamp(entry),
                )
                articles.append(article)
            except Exception as e:
                print(f"Skipping invalid RSS entry ({getattr(entry, 'link', '?')}): {e}")

    return articles

def _parse_rss_timestamp(entry) -> datetime | None:
    """RSS gives timestamps in RFC 822 format (e.g. 'Sat, 11 Jul 2026 09:36:03 GMT'),
    which Pydantic's datetime parser can't read directly. feedparser already
    breaks this down into a struct_time for us in `published_parsed` — we just
    convert that into a proper timezone-aware Python datetime."""
    if not hasattr(entry, "published_parsed") or entry.published_parsed is None:
        return None
    timestamp = calendar.timegm(entry.published_parsed)
    return datetime.fromtimestamp(timestamp, UTC)

def delivery_report(err, msg):
    """Called automatically by Kafka once a message is either confirmed
    delivered or fails. This is NOT called immediately when you call
    .produce() — only later, when .poll() or .flush() processes it."""
    if err is not None:
        print(f"Delivery failed for {msg.key()}: {err}")
    else:
        print(f"Delivered to {msg.topic()} [partition {msg.partition()}]")


def publish_article(article: RawArticle) -> None:
    """Publishes one RawArticle to the raw-news topic as a JSON message.
    The article's own id is used as the Kafka message key — this means
    all messages for the same article id would land on the same partition,
    useful if we ever need ordered processing per-article."""
    kafka_producer.produce(
        topic="raw-news",
        key=str(article.id),
        value=article.model_dump_json(),
        callback=delivery_report,
    )
    kafka_producer.poll(0)

import time


def run_once() -> int:
    """Runs a single fetch-validate-dedupe-publish cycle. Returns the number
    of new articles published, so the caller can log it."""
    newsapi_results = fetch_newsapi_articles(page_size=5)
    rss_results = fetch_rss_articles()

    all_articles = newsapi_results + rss_results
    new_articles = [a for a in all_articles if not is_duplicate(a.url)]

    for a in new_articles:
        print(f"- [{a.source}] {a.title}")
        publish_article(a)

    kafka_producer.flush()
    return len(new_articles)


def run_forever(interval_seconds: int = 60) -> None:
    """Runs fetch cycles repeatedly, sleeping between each one, until
    interrupted with Ctrl+C."""
    print(f"News Producer starting — fetching every {interval_seconds}s. Press Ctrl+C to stop.\n")
    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"[cycle {cycle}] {time.strftime('%Y-%m-%d %H:%M:%S')} — fetching...")
            try:
                count = run_once()
                print(f"[cycle {cycle}] published {count} new articles\n")
            except Exception as e:
                # A single bad cycle (e.g. NewsAPI temporarily down) shouldn't
                # kill the whole service — log it and keep going.
                print(f"[cycle {cycle}] ERROR during fetch cycle: {e}\n")

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        kafka_producer.flush()
        print("Done.")


if __name__ == "__main__":
    run_forever(interval_seconds=60)
