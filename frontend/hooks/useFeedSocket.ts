"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "@/lib/api";
import type { Article, FeedSocketMessage } from "@/lib/types";

export type SocketStatus = "connecting" | "open" | "closed";

interface Options {
  /** called once per new article pushed from /ws/feed */
  onArticle?: (article: Partial<Article> & { id: string; title: string }) => void;
  enabled?: boolean;
}

/**
 * Subscribes to the backend /ws/feed stream. Reconnects with capped
 * exponential backoff. Returns the live connection status.
 */
export function useFeedSocket({ onArticle, enabled = true }: Options): {
  status: SocketStatus;
} {
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const onArticleRef = useRef(onArticle);
  onArticleRef.current = onArticle;

  useEffect(() => {
    if (!enabled) return;

    let ws: WebSocket | null = null;
    let retry = 0;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let stopped = false;

    const connect = () => {
      setStatus(retry === 0 ? "connecting" : "connecting");
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        retry = 0;
        setStatus("open");
      };

      ws.onmessage = (ev) => {
        let msg: FeedSocketMessage;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (msg.type === "article" && msg.data?.id) {
          onArticleRef.current?.(msg.data);
        }
      };

      ws.onclose = () => {
        setStatus("closed");
        if (stopped) return;
        const delay = Math.min(1000 * 2 ** retry, 15000);
        retry += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onerror = () => ws?.close();
    };

    connect();

    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [enabled]);

  return { status };
}
