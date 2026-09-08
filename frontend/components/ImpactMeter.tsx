/** Compact 0–10 impact indicator: 5 pips + the number. High impact (>=8)
 *  reads amber to match the alerts threshold. */
export function ImpactMeter({ score }: { score: number }) {
  const pips = Math.round(Math.max(0, Math.min(10, score)) / 2); // 0..5
  const hot = score >= 8;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-muted"
      title={`Impact score ${score}/10`}
    >
      <span className="flex gap-0.5" aria-hidden>
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className={`h-2.5 w-1 rounded-sm ${
              i < pips
                ? hot
                  ? "bg-amber-500"
                  : "bg-foreground/50"
                : "bg-border"
            }`}
          />
        ))}
      </span>
      <span className={`tabular-nums font-medium ${hot ? "text-amber-500" : ""}`}>
        {score}
      </span>
    </span>
  );
}
