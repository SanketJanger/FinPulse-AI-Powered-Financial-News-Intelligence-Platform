// TypeScript mirrors of the backend Pydantic response models
// (backend/app/schemas/article.py). Keep field names identical to the API.

export type Sentiment = "bullish" | "bearish" | "neutral";

export interface Article {
  id: string;
  title: string;
  description: string | null;
  content: string | null;
  url: string;
  source: string;
  author: string | null;
  published_at: string | null; // ISO 8601
  fetched_at: string;

  // V2 — FinBERT
  sentiment: Sentiment | null;
  confidence: number | null;
  impact_score: number | null;
  processed_at: string | null;

  // V3 — hybrid pipeline
  summary: string | null;
  tickers: string[] | null;
  companies: string[] | null;
  category: string | null;
  embedding_id: string | null;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface FeedResponse {
  items: Article[];
  meta: PageMeta;
}

export interface SourceCount {
  source: string;
  count: number;
}

export interface TrendingResponse {
  window_hours: number;
  total_articles: number;
  top_sources: SourceCount[];
}

export interface SentimentDayStats {
  date: string; // YYYY-MM-DD
  bullish: number;
  bearish: number;
  neutral: number;
  total: number;
}

export interface SentimentStatsResponse {
  generated_at: string;
  days: SentimentDayStats[];
}

export interface SearchHit {
  score: number; // cosine similarity in [0, 1]
  article: Article;
}

export interface SearchResponse {
  query: string;
  count: number;
  hits: SearchHit[];
}

export interface AlertsResponse {
  threshold: number;
  count: number;
  alerts: Article[];
}

export interface HealthResponse {
  api: string;
  redis: string;
  kafka: string;
  database: string;
  kafka_topics?: string[] | null;
}

// Shape pushed over /ws/feed: {"type":"connected"} then
// {"type":"article","data": <article-ish JSON>} per new row.
export type FeedSocketMessage =
  | { type: "connected" }
  | { type: "article"; data: Partial<Article> & { id: string; title: string } };
