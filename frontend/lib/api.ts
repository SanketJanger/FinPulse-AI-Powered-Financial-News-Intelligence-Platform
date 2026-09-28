import type {
  AlertsResponse,
  Article,
  FeedResponse,
  SearchResponse,
  SentimentStatsResponse,
  Sentiment,
  TrendingResponse,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

/** ws:// or wss:// URL for the real-time feed. */
export const WS_URL = `${API_URL.replace(/^http/, "ws")}/ws/feed`;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new ApiError(0, `Can't reach the API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  }
  const str = s.toString();
  return str ? `?${str}` : "";
}

export interface FeedParams {
  page?: number;
  pageSize?: number;
  source?: string;
  sentiment?: Sentiment;
  dateFrom?: string;
  dateTo?: string;
}

export const api = {
  health: () => request("/health"),

  getFeed: (p: FeedParams = {}) =>
    request<FeedResponse>(
      `/api/feed${qs({
        page: p.page,
        page_size: p.pageSize,
        source: p.source,
        sentiment: p.sentiment,
        date_from: p.dateFrom,
        date_to: p.dateTo,
      })}`,
    ),

  getArticle: (id: string) => request<Article>(`/api/article/${id}`),

  getTrending: (windowHours = 24, limit = 8) =>
    request<TrendingResponse>(`/api/trending${qs({ window_hours: windowHours, limit })}`),

  getSentimentStats: (days = 7) =>
    request<SentimentStatsResponse>(`/api/sentiment/stats${qs({ days })}`),

  getAlerts: (limit = 10) =>
    request<AlertsResponse>(`/api/alerts${qs({ limit })}`),

  search: (query: string, k = 8, sentiment?: Sentiment) =>
    request<SearchResponse>(`/api/search`, {
      method: "POST",
      body: JSON.stringify({ query, k, sentiment }),
    }),
};
