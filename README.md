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

## Next: Phase 2 — Data Ingestion
Once `/health` returns clean, we'll build the News Producer service that pulls
from NewsAPI + RSS feeds and publishes to `raw-news`. That's when you'll need
a NewsAPI key (free tier: https://newsapi.org/register).
