# FinPulse — Phase 1: Infrastructure Setup

## Prerequisites (Linux)
- Docker + Docker Compose v2 (`docker compose version` should work, not the old `docker-compose`)
- Python 3 — any recent version is fine (3.10–3.12). Check with `python3 --version`.
  You do NOT need python3.11 specifically; the instructions below use whatever
  `python3` resolves to on your system, inside a venv.

## 1. Copy environment file
```bash
cp .env.example .env
```
Leave the API keys blank for now — Phase 1 needs none of them.

## 2. Bring up infrastructure
```bash
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```
This starts Kafka (KRaft mode, no Zookeeper), Redis, and Kafka UI, then creates
the three topics (`raw-news`, `processed-news`, `alerts`).

Verify:
- Kafka UI: http://localhost:8080 — you should see the finpulse cluster and 3 topics
- Redis: the script runs a `PING` and should print `PONG`

## 3. Run the backend skeleton
```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # your prompt should now show (venv)
pip install -r requirements.txt
uvicorn app.main:app --reload
```
**Important:** if `uvicorn` starts but `/health` still shows `ModuleNotFoundError`,
your shell is not actually inside the venv (or a previous non-venv attempt left a
process running). Check that `which python` and `which uvicorn` both point inside
`backend/venv/bin/`, kill any stray `uvicorn` process, and re-run the command above.

Ubuntu's system Python is "externally managed" (PEP 668) — you cannot
`pip install` outside a venv without `--break-system-packages`. Always use the
venv here rather than overriding that.

## 4. Verify end-to-end
```bash
curl localhost:8000/health
```
Expected:
```json
{
  "api": "ok",
  "redis": "ok",
  "kafka": "ok",
  "kafka_topics": ["raw-news", "processed-news", "alerts"]
}
```

If `kafka` shows an error, double check `KAFKA_BOOTSTRAP_SERVERS=localhost:9094` in `.env`
matches the `EXTERNAL` listener in `docker-compose.yaml`.

## Troubleshooting

**`failed to resolve reference docker.io/bitnami/kafka:3.6`**
Bitnami removed several legacy image tags from Docker Hub in 2025. This project
now uses `apache/kafka:3.7.0` (the official Apache image) instead — already
fixed in this `docker-compose.yaml`. If you still see this error, run
`docker compose pull` to refresh, or check you unzipped the latest version.

**`Command 'python3.11' not found`**
Use `python3` instead — see Prerequisites above. Any 3.10+ works fine for this
project; nothing here is 3.11-specific.

**`error: externally-managed-environment` from pip**
You're installing outside a venv. Activate the venv first (`source venv/bin/activate`)
and re-run `pip install`. Don't use `--break-system-packages` — it installs into
system Python and will cause exactly the "it ran but with the wrong Python" issue
you'd hit if `uvicorn` picks up the system install instead of the venv one.

## What's NOT in Phase 1
No AI, no news ingestion yet, no database writes. This phase only proves the
plumbing (Kafka + Redis + FastAPI) works together. Phase 2 adds the News Producer.

---

# Phase 4 — Backend API (V1)

The deployable V1: a read API over the articles Postgres stores, plus a
real-time WebSocket feed. No AI yet.

## Run the whole pipeline locally

```bash
# 1. infra (from Phase 1)
./scripts/setup-local.sh

# 2. API
cd backend && source venv/bin/activate
uvicorn app.main:app --reload            # http://localhost:8000/docs

# 3. consumer — drains raw-news into Postgres, fans new rows out to /ws/feed
python -m app.services.ai_consumer

# 4. producer — pulls NewsAPI + RSS, publishes to raw-news (needs NEWSAPI_KEY)
python -m app.services.news_producer
```

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | api / redis / kafka / database status (never 5xx) |
| GET | `/api/feed` | `page` (≥1), `page_size` (1–100), `source`, `date_from`, `date_to` (ISO). Cached in Redis for `FEED_CACHE_TTL` s (default 60); response carries `X-Cache: HIT\|MISS` |
| GET | `/api/article/{id}` | UUID path; 422 on malformed id, 404 if absent |
| GET | `/api/trending` | `window_hours` (1–168, default 24), `limit` (1–50). Top sources by volume in the window. Cached like `/api/feed` |
| WS | `/ws/feed` | Emits `{"type":"connected"}` then `{"type":"article","data":{…}}` for every newly-stored article |

Ordering / date filtering use `coalesce(published_at, fetched_at)` so RSS
rows with no publisher timestamp still sort and filter sensibly.

## Error contract

- **422** — bad query/path params: `{"detail": [ …pydantic errors… ]}`
- **404** — `GET /api/article/{id}` for a well-formed but unknown UUID: `{"detail": "Article … not found"}`
- **500** — anything unhandled: `{"detail": "Internal server error"}` (full traceback stays in the server log)

## Config (added this phase, all optional)

| Env var | Default | Meaning |
|---------|---------|---------|
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list of allowed browser origins |
| `FEED_CACHE_TTL` | `60` | seconds `/api/feed` and `/api/trending` stay cached |
| `NEW_ARTICLES_CHANNEL` | `finpulse:new-articles` | Redis pub/sub channel bridging consumer → `/ws/feed` |

## Next: Phase 5 — FinBERT sentiment (V2)
