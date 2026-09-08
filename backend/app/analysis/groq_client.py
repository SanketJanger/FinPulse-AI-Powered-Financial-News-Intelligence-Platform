"""
Groq LLM client — a 2-sentence summary + a coarse category for one article,
in a single chat call that returns JSON.

Design points the pipeline depends on:
- `available` is False when no API key is configured; callers skip it.
- One client-side throttle (`groq_min_interval_ms`) keeps us under the
  free-tier rate limit; a 429 is retried once, honouring Retry-After.
- Any failure returns None — the article is still stored, just without a summary.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger("finpulse.groq")

CATEGORIES = (
    "markets",
    "earnings",
    "monetary-policy",
    "mergers-acquisitions",
    "regulation",
    "crypto",
    "energy",
    "tech",
    "macro",
    "other",
)

_SYSTEM = (
    "You are a financial news editor. Given a headline and blurb, reply with "
    "a compact JSON object and nothing else: "
    '{"summary": "<exactly two plain sentences>", "category": "<one of: '
    + ", ".join(CATEGORIES)
    + '>"}. The summary must be factual, no opinion, no preamble.'
)


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    category: str


class GroqSummarizer:
    def __init__(self, api_key: str, model: str, min_interval_ms: int = 2100):
        self.model = model
        self._min_interval = min_interval_ms / 1000.0
        self._api_key = api_key or ""
        self._client = None
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self):
        if self._client is None:
            from groq import AsyncGroq

            self._client = AsyncGroq(api_key=self._api_key)
        return self._client

    async def _throttle(self) -> None:
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)

    async def summarize(self, title: str, description: str | None) -> SummaryResult | None:
        if not self.available:
            return None

        user = f"Headline: {title}\nBlurb: {description or '(none)'}"
        try:
            client = self._ensure_client()
        except Exception:
            logger.exception("groq client init failed")
            return None

        # gpt-oss models spend completion tokens on a reasoning trace before
        # the answer; keep that minimal so short summaries stay fast and
        # cheap on the free tier.
        extra_body = {"reasoning_effort": "low"} if "gpt-oss" in self.model else {}

        async with self._lock:  # serialise calls so the throttle is meaningful
            for attempt in (1, 2):
                await self._throttle()
                try:
                    resp = await client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": _SYSTEM},
                            {"role": "user", "content": user},
                        ],
                        temperature=0,
                        max_tokens=512,
                        extra_body=extra_body,
                    )
                    self._last_call = time.monotonic()
                    return _parse(resp.choices[0].message.content)
                except Exception as exc:  # noqa: BLE001
                    self._last_call = time.monotonic()
                    retry_after = _retry_after(exc)
                    if attempt == 1 and retry_after is not None:
                        logger.warning("groq rate-limited, retrying in %.1fs", retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    logger.warning("groq summarize failed (%s) — storing without summary", exc)
                    return None
        return None


def _parse(raw: str) -> SummaryResult | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:].lstrip() if text.lower().startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        summary = str(data["summary"]).strip()
        category = str(data.get("category", "other")).strip().lower()
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("groq returned unparseable content: %r", raw[:200])
        return None
    if category not in CATEGORIES:
        category = "other"
    return SummaryResult(summary=summary, category=category) if summary else None


def _retry_after(exc: Exception) -> float | None:
    """Pull a Retry-After (seconds) off a Groq RateLimitError, if present."""
    resp = getattr(exc, "response", None)
    if resp is None or getattr(resp, "status_code", None) != 429:
        return None
    try:
        return float(resp.headers.get("retry-after", "2"))
    except (TypeError, ValueError):
        return 2.0
