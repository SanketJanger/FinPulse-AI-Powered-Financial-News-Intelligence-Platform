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

---

# Database migrations (Alembic)

The schema is managed by Alembic (`backend/alembic/`). A fresh environment
builds the whole schema with one command; nothing is created implicitly at
app startup.

```bash
cd backend && source venv/bin/activate

alembic upgrade head        # build / update schema to latest
alembic history             # list migrations
alembic current             # what this DB is at
alembic downgrade -1        # roll back one
```

The DB URL comes from `DATABASE_URL` in `.env` (read by `alembic/env.py`),
not from `alembic.ini`. `alembic check` fails CI if the ORM in
`app/models/database.py` has drifted from the migrations.

Migrations:
- `0001_initial_articles` — baseline `articles` table (Phase 3 schema)
- `0002_add_v2_sentiment_columns` — adds `sentiment`, `confidence`, `impact_score`, `processed_at`
- `0003_add_v3_columns` — adds `summary`, `tickers`, `companies`, `category`, `embedding_id`

> If you already ran Phase 3 (so `articles` exists but there's no
> `alembic_version` table), stamp the baseline once before upgrading:
> `alembic stamp 0001_initial_articles && alembic upgrade head`.

---

# Phase 5 — FinBERT sentiment (V2)

Adds a sentiment pass to the consumer, switched on by `PROCESSOR_VERSION`.
No API or schema rewrite — just new nullable columns and endpoints.

## Switch versions

```bash
# v1 — pass-through, no ML deps needed
PROCESSOR_VERSION=v1 python -m app.services.ai_consumer

# v2 — FinBERT sentiment (needs torch + transformers)
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
pip install transformers==4.44.2
PROCESSOR_VERSION=v2 python -m app.services.ai_consumer
```

The FinBERT model (`ProsusAI/finbert`, ~440 MB) loads **once** at consumer
startup — GPU if `torch.cuda.is_available()`, else CPU. If the model fails
to load or score an article, the article is still stored, just with
`sentiment = NULL`.

## Backfill existing rows

```bash
PROCESSOR_VERSION=v2 python -m app.services.backfill          # un-enriched rows only
PROCESSOR_VERSION=v3 python -m app.services.backfill --all    # re-run everything
#                                            [--limit N] [--batch N]
```
Runs the current processor over rows already in Postgres and updates them
in place — use it when rolling a new version out over old data, or after
changing an enrichment rule.

## Enrichment

`ProsusAI/finbert` labels (`positive`/`negative`/`neutral`) are surfaced as
`bullish`/`bearish`/`neutral`. `impact_score`:

| sentiment | impact_score |
|-----------|--------------|
| neutral | **3** (floored — no directional signal) |
| bullish / bearish, confidence > 0.9 | 8 |
| bullish / bearish, confidence > 0.8 | 6 |
| bullish / bearish, confidence > 0.7 | 5 |
| bullish / bearish, else | 3 |

## New / changed endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/feed` | + `sentiment=bullish\|bearish\|neutral` filter (422 on any other value) |
| GET | `/api/article/{id}` | response now carries `sentiment`, `confidence`, `impact_score`, `processed_at` (null under v1) |
| GET | `/api/sentiment/stats` | `days` (1–90, default 7). Daily `{bullish, bearish, neutral, total}` buckets (UTC), over rows with `processed_at` set. Cached `SENTIMENT_STATS_TTL` s (default 300) |

## Config (added this phase)

| Env var | Default | Meaning |
|---------|---------|---------|
| `PROCESSOR_VERSION` | `v1` | `v1` pass-through · `v2` FinBERT · `v3` hybrid |
| `FINBERT_MODEL` | `ProsusAI/finbert` | HF model id for v2 |
| `SENTIMENT_STATS_TTL` | `300` | `/api/sentiment/stats` cache seconds |

---

# Phase 6 — Hybrid AI (V3)

The consumer's v3 processor chains four steps per article; each is
independently guarded, so only FinBERT is a hard dependency:

```
FinBERT       -> sentiment / confidence / impact_score
Groq (1 call) -> 2-sentence summary + category            (skipped if no GROQ_API_KEY)
regex + spaCy -> tickers / companies
MiniLM (384d) -> embedding -> upsert to ChromaDB          embedding_id = article id
```

## Run V3

```bash
pip install groq==0.11.0 spacy==3.7.6 sentence-transformers==3.1.1 chromadb==0.5.5
python -m spacy download en_core_web_sm

docker compose --profile v3 up -d chromadb        # vector DB on :8000
export GROQ_API_KEY=gsk_...                        # optional — blank => no summaries
PROCESSOR_VERSION=v3 python -m app.services.ai_consumer
```

The API process also loads the MiniLM model + connects to ChromaDB at
startup (for `POST /api/search`). If either is missing, `/api/search`
returns **503**; every other endpoint is unaffected.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/search` | body `{query, k=5 (1–50), sentiment?}`. Embeds the query, cosine-kNN in ChromaDB, hydrates hits from Postgres. Returns `{query, count, hits:[{score, article}]}`, `score` = `1 − cosine_distance` ∈ [0,1], ordered high→low. 503 if search unavailable |
| GET | `/api/alerts` | `limit` (1–200, default 50), `since` (ISO). Articles with `impact_score >= ALERT_IMPACT_THRESHOLD`, newest first. Returns `{threshold, count, alerts:[…]}` |
| GET | `/api/article/{id}` · `/api/feed` | responses now also carry `summary`, `tickers`, `companies`, `category`, `embedding_id` |

## Alerts

When an enriched article scores `impact_score >= ALERT_IMPACT_THRESHOLD`
(default 8) the consumer publishes a compact JSON alert to the Kafka
**`alerts`** topic (streaming interface for downstream notifiers).
`GET /api/alerts` is the durable view, read straight from the `articles`
table so it can't drift from what triggered the alert.

## Graceful degradation

| Failure | Result |
|---------|--------|
| No `GROQ_API_KEY` / Groq 4xx-5xx / rate limit (retried once) | article stored, `summary` + `category` NULL |
| spaCy / regex error | `tickers`/`companies` NULL, rest proceeds |
| ChromaDB down | embedding still computed, not stored, `embedding_id` NULL; `/api/search` → 503 |
| FinBERT down | (hard dep) sentiment NULL, article still stored |

## Config (added this phase)

| Env var | Default | Meaning |
|---------|---------|---------|
| `GROQ_API_KEY` | — | Groq key; blank disables summaries |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | summary model |
| `GROQ_MIN_INTERVAL_MS` | `2100` | client-side throttle between Groq calls |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 384-dim |
| `CHROMA_HOST` / `CHROMA_PORT` | `localhost` / `8000` | ChromaDB |
| `CHROMA_COLLECTION` | `articles` | collection name (cosine space) |
| `ALERT_IMPACT_THRESHOLD` | `8` | `impact_score >=` this → `alerts` topic |
