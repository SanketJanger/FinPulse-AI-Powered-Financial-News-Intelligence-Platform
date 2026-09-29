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
