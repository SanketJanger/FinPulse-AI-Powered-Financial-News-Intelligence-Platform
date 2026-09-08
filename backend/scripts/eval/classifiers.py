"""
The three systems under evaluation, behind a common interface:

    clf.name           -> str
    clf.predict(text)  -> (label, latency_seconds)

- VADER   : lexicon baseline (vaderSentiment), compound-score thresholds
- FinBERT : the production model (app.analysis.finbert.FinBERTAnalyzer)
- GroqLLM : gpt-oss-120b, zero-shot 3-way classification via the same rubric
"""
from __future__ import annotations

import json
import time

from scripts.eval.labeler import RUBRIC

LABELS = ("bullish", "bearish", "neutral")


class VaderClassifier:
    name = "VADER"

    def __init__(self, pos=0.05, neg=-0.05):
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._an = SentimentIntensityAnalyzer()
        self.pos, self.neg = pos, neg

    def predict(self, text: str) -> tuple[str, float]:
        t0 = time.perf_counter()
        compound = self._an.polarity_scores(text)["compound"]
        dt = time.perf_counter() - t0
        if compound > self.pos:
            return "bullish", dt
        if compound < self.neg:
            return "bearish", dt
        return "neutral", dt


class FinbertClassifier:
    name = "FinBERT"

    def __init__(self):
        from app.analysis.finbert import FinBERTAnalyzer

        self._an = FinBERTAnalyzer()
        self._an.load()

    def predict(self, text: str) -> tuple[str, float]:
        t0 = time.perf_counter()
        res = self._an.analyze(text)
        dt = time.perf_counter() - t0
        # FinBERTAnalyzer already maps positive/negative/neutral -> bullish/bearish/neutral
        return res.label, dt


class GroqLLMClassifier:
    name = "Groq gpt-oss-120b"

    _SYSTEM = (
        RUBRIC
        + '\nReturn only the JSON object, e.g. {"label":"bearish","confidence":0.8,"rationale":"..."}.'
    )

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b", min_interval_s: float = 3.0):
        from groq import Groq

        self._client = Groq(api_key=api_key)
        self.model = model
        self.min_interval = min_interval_s
        self._last = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)

    def _call(self, text: str):
        return self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._SYSTEM},
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=512,
            extra_body={"reasoning_effort": "low"},
        )

    def predict(self, text: str) -> tuple[str, float]:
        self._throttle()
        t0 = time.perf_counter()
        raw = None
        for attempt in (1, 2, 3):
            try:
                resp = self._call(text)
                self._last = time.monotonic()
                raw = resp.choices[0].message.content or ""
                break
            except Exception as exc:  # noqa: BLE001
                self._last = time.monotonic()
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status == 429 and attempt < 3:
                    hdrs = getattr(getattr(exc, "response", None), "headers", {}) or {}
                    wait = float(hdrs.get("retry-after", 20) or 20)
                    print(f"    · Groq 429, waiting {wait:.0f}s (attempt {attempt})")
                    time.sleep(min(wait + 1, 65))
                    continue
                print(f"    ! Groq error: {str(exc)[:120]}")
                return "neutral", time.perf_counter() - t0

        dt = time.perf_counter() - t0
        if not raw:
            return "neutral", dt
        s, e = raw.find("{"), raw.rfind("}")
        try:
            data = json.loads(raw[s : e + 1]) if s != -1 else {}
        except json.JSONDecodeError:
            data = {}
        label = str(data.get("label", "neutral")).strip().lower()
        return (label if label in LABELS else "neutral"), dt
