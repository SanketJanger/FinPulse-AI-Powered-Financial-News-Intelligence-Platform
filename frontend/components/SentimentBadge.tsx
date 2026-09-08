import type { Sentiment } from "@/lib/types";

// bullish = green, bearish = red, neutral = gray. The label text is always
// shown, so colour is never the only signal (CVD-safe).
const STYLES: Record<Sentiment, string> = {
  bullish:
    "bg-bullish/12 text-bullish ring-1 ring-inset ring-bullish/30",
  bearish:
    "bg-bearish/12 text-bearish ring-1 ring-inset ring-bearish/30",
  neutral:
    "bg-neutral/12 text-neutral ring-1 ring-inset ring-neutral/30",
};

const DOT: Record<Sentiment, string> = {
  bullish: "bg-bullish",
  bearish: "bg-bearish",
  neutral: "bg-neutral",
};

export function SentimentBadge({
  sentiment,
  confidence,
  size = "sm",
}: {
  sentiment: Sentiment | null;
  confidence?: number | null;
  size?: "sm" | "xs";
}) {
  if (!sentiment) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-neutral/10 px-2 py-0.5 text-xs text-muted">
        unscored
      </span>
    );
  }
  const pad = size === "xs" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium capitalize ${pad} ${STYLES[sentiment]}`}
      title={
        confidence != null
          ? `${sentiment} · ${(confidence * 100).toFixed(0)}% confidence`
          : sentiment
      }
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[sentiment]}`} />
      {sentiment}
      {confidence != null && (
        <span className="tabular-nums opacity-70">{(confidence * 100).toFixed(0)}%</span>
      )}
    </span>
  );
}
