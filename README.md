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
![FinPulse Architecture](Architecture%20Diagram/finpulse_architecture.png)


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

## API Endpoints

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

RAG semantic search: Precision@5 0.38, MRR 0.622, query latency 4.5ms.
