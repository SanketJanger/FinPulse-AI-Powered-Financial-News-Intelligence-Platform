# FinPulse - AI-Powered Financial News Intelligence Platform

Real-time financial news intelligence platform with hybrid AI analysis.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![Kafka](https://img.shields.io/badge/Kafka-3.7-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Overview

FinPulse processes 500+ financial news articles per hour from 17 sources, enriching each with sentiment analysis, AI-generated summaries, and semantic embeddings. The hybrid AI architecture uses specialized models for each task: FinBERT for sentiment (22ms), Groq LLaMA 3.3 for summaries, and sentence-transformers for RAG-based semantic search.

## Features

- **Real-time streaming** via Apache Kafka (KRaft mode)
- **Hybrid AI pipeline**: FinBERT sentiment, Groq summaries, SpaCy ticker extraction
- **Semantic search**: Natural language queries like "Fed impact on tech stocks"
- **Live dashboard**: WebSocket updates, sentiment filters, dark mode
- **High-impact alerts**: Articles with market-moving potential (score >= 8)

## Architecture
![FinPulse Architecture](Architecture%20diagram/finpulse_architecture_diagram.png)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Streaming | Apache Kafka (KRaft) |
| Backend | FastAPI, Python 3.11 |
| AI/ML | FinBERT, Groq LLaMA 3.3, SpaCy, sentence-transformers |
| Vector DB | ChromaDB |
| Database | PostgreSQL |
| Cache | Redis |
| Frontend | Next.js 14, Tailwind CSS |
| Infrastructure | Docker Compose |

## Quickstart

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+
- Groq API key (free at console.groq.com)
- NewsAPI key (optional, free at newsapi.org)

### Setup

```bash
# Clone
git clone https://github.com/SanketJanger/Finpulse.git
cd Finpulse

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env
cat > .env << EOF
GROQ_API_KEY=your_groq_key
NEWSAPI_KEY=your_newsapi_key
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finpulse
REDIS_URL=redis://localhost:6379
CHROMA_HOST=localhost
CHROMA_PORT=8002
EOF

# Frontend
cd ../frontend
npm install

# Start infrastructure
cd ..
docker compose --profile v3 up -d
```

### Run

Terminal 1 - Backend API:
```bash
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2 - AI Consumer:
```bash
cd backend && source venv/bin/activate
PROCESSOR_VERSION=v3 python -m app.services.ai_consumer
```

Terminal 3 - News Producer:
```bash
cd backend && source venv/bin/activate
python -m app.services.news_producer
```

Terminal 4 - Frontend:
```bash
cd frontend
npm run dev
```

Open http://localhost:3000

<<<<<<< HEAD
## API Endpoints
=======
Migrations:
- `0001_initial_articles` — baseline `articles` table (Phase 3 schema)
- `0002_add_v2_sentiment_columns` — adds `sentiment`, `confidence`, `impact_score`, `processed_at`
- `0003_add_v3_columns` — adds `summary`, `tickers`, `companies`, `category`, `embedding_id`
>>>>>>> phase-8-evaluation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/feed` | GET | Paginated news feed with filters |
| `/api/article/{id}` | GET | Single article with full details |
| `/api/search` | POST | Semantic search via RAG |
| `/api/trending` | GET | Top news sources by volume |
| `/api/sentiment/stats` | GET | Sentiment distribution |
| `/api/alerts` | GET | High-impact articles (score >= 8) |
| `/ws/feed` | WS | Real-time article updates |
| `/health` | GET | Service health check |

## Evaluation Results

Sentiment analysis comparison on 200 financial news articles:

| Model | Accuracy | Macro F1 | Latency |
|-------|----------|----------|---------|
| VADER (baseline) | 44.0% | 0.441 | 0.3ms |
| **FinBERT** | **62.5%** | **0.620** | **22ms** |
| Groq LLM | 78.0% | 0.784 | 646ms |

FinBERT delivers 18.5 percentage points improvement over VADER at 30x lower latency than LLM.

<<<<<<< HEAD
RAG semantic search: Precision@5 0.38, MRR 0.622, query latency 4.5ms.
=======
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
| `CHROMA_HOST` / `CHROMA_PORT` | `localhost` / `8002` | ChromaDB (host 8002 → container 8000) |
| `CHROMA_COLLECTION` | `articles` | collection name (cosine space) |
| `ALERT_IMPACT_THRESHOLD` | `8` | `impact_score >=` this → `alerts` topic |

---

# Phase 7 — Next.js frontend

`frontend/` — Next.js 14 (App Router, TypeScript, Tailwind). A single-page
dashboard over the backend API with a live feed.

## Run

```bash
cd frontend
npm install
cp .env.example .env.local          # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                          # http://localhost:3000
```

The backend API must be running on `NEXT_PUBLIC_API_URL` (`uvicorn app.main:app`).
For the live feed and `/api/search` to have anything to show, also run the
consumer and, ideally, `PROCESSOR_VERSION=v3`.

## What's on the page

| Component | Source | Notes |
|-----------|--------|-------|
| `NewsFeed` | `GET /api/feed` | pagination ("Load more"), sentiment filter chips; prepends websocket pushes with a highlight |
| `ArticleCard` | — | title, source, relative time, category, summary, `SentimentBadge`, `ImpactMeter`, `$TICKER` chips |
| `SentimentBadge` | — | bullish = green, bearish = red, neutral = gray (label always shown → CVD-safe) |
| `SearchBar` → `SearchResults` | `POST /api/search` | semantic search; `?q=` in the URL runs a search on load; each hit shows a `% match` |
| `TrendingSidebar` | `GET /api/trending` | top sources (24h) with volume bars |
| `SentimentStats` | `GET /api/sentiment/stats` | stacked bar per day + legend + hover + table view |
| `AlertsBanner` | `GET /api/alerts` | dismissible strip of high-impact headlines |
| `useFeedSocket` | `WS /ws/feed` | reconnects with backoff; drives the header "live" indicator |

- **Types** (`lib/types.ts`) mirror the backend Pydantic response models.
- **API client** (`lib/api.ts`) — one function per endpoint, typed, with an
  `ApiError` that carries the status (search shows a specific message on 503).
- **Responsive** — two-column ≥ `lg`, single column with the sidebar below on mobile.
- **Dark mode** — follows `prefers-color-scheme`, toggle persists to `localStorage`,
  no flash (inline script in `<head>`).
- Loading = skeletons; errors = inline message + Retry.

## Config

| Env var | Default | Meaning |
|---------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | backend base URL; `ws(s)://…/ws/feed` is derived from it |

---

# Phase 8 — Evaluation (VADER vs FinBERT vs Groq LLM + RAG)

`backend/scripts/evaluation.py` — compares three sentiment classifiers
against an independent reference and evaluates the semantic-search
retrieval. Everything is written to `backend/eval_output/` as CSV/JSON/PNG.

## Run

```bash
cd backend && source venv/bin/activate
pip install openai vaderSentiment pandas matplotlib seaborn scikit-learn
export OPENAI_API_KEY=sk-...          # ground-truth labeller + RAG judge (gpt-4o-mini)
# GROQ_API_KEY must also be set (LLM classifier under test)
docker compose --profile v3 up -d chromadb

python -m scripts.evaluation --n 200
# resume without re-spending API calls:
python -m scripts.evaluation --reuse-labels --reuse-predictions
python -m scripts.evaluation --reuse-labels --skip-rag
```

## Design

| | |
|---|---|
| **Test set** | `--n` articles from Postgres, stratified by source, fixed seed (`scripts/eval/dataset.py`) |
| **Ground truth** | OpenAI `gpt-4o-mini` (not a system under test) + a fixed market-impact rubric; each item labelled twice (temp 0 / temp 0.5) → `gt_stable` flag; metrics reported on full set **and** stable subset |
| **Classifiers** | VADER (`compound` thresholds), FinBERT (`app.analysis.finbert`), Groq `openai/gpt-oss-120b` (zero-shot, same rubric) — common `predict(text) → (label, latency)` interface |
| **Metrics** | accuracy, macro/weighted P/R/F1, per-class F1, confusion matrix, Cohen's κ vs GT, latency mean/median/p95 (`sklearn`) |
| **RAG** | 20 topical queries → dedicated ChromaDB collection of the test set → `gpt-4o-mini` judges each top-10 hit → Precision@5, Precision@10, MRR |

## Artefacts (`backend/eval_output/`)

| File | Contents |
|------|----------|
| `test_set.csv` | `article_id, title, content, ground_truth_sentiment, gt_confidence, gt_stable, gt_rationale, source, url` |
| `predictions.csv` | per-article predictions + latencies, all 3 models + GT |
| `metrics.json` | full metric objects (full set + stable subset) |
| `rag_judgements.csv` | per `(query, hit)` relevance + similarity |
| `rag_metrics.json` | P@5 / P@10 / MRR overall + per query |
| `figures/*.png` | confusion matrices, model comparison, per-class F1, latency (150 dpi) |
| `EVALUATION_REPORT.md` | the full write-up, incl. a Threats-to-validity section |

## Config

| Env var | Default | Meaning |
|---------|---------|---------|
| `OPENAI_API_KEY` | — | ground-truth labeller + RAG judge |
| `EVAL_LABEL_MODEL` | `gpt-4o-mini` | |
| `EVAL_GROQ_MODEL` | `openai/gpt-oss-120b` | LLM classifier under test |
>>>>>>> phase-8-evaluation
