"""
Ground-truth labelling with OpenAI gpt-4o-mini.

This model is NOT one of the systems under test (VADER, FinBERT, Groq
gpt-oss-120b), which keeps the reference labels independent of the
classifiers being scored.

Protocol per article:
  - pass A: temperature 0   (deterministic)
  - pass B: temperature 0.5 (self-consistency probe)
  final label  = pass A
  stable flag  = (pass A == pass B)
Metrics are reported on the full set and on the stable subset.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from openai import OpenAI

RUBRIC = """You label financial-news items by their MARKET-IMPACT sentiment for the \
primary company, asset, sector, or market the item is about.

Return exactly one label:
- "bullish": the news implies upward price pressure or reflects clearly positive \
fundamentals (beats, upgrades, strong guidance, favourable policy, demand strength, \
successful launches, rising margins, deal closes at a premium).
- "bearish": the news implies downward price pressure or clearly negative \
fundamentals (misses, downgrades, weak guidance, layoffs, probes/lawsuits, \
demand weakness, supply shocks that hurt the subject, defaults, cuts).
- "neutral": factual/administrative, mixed signals that roughly cancel, opinion/analysis \
with no directional call, macro context with no clear implication for the subject, or \
sentiment that cannot be determined from the text.

Rules:
- Judge the effect on the SUBJECT of the story, not on the reader's mood.
- "Stocks rise/fall today" market-wrap items: label by the net direction stated.
- If genuinely torn between neutral and a direction, choose neutral.
Respond as JSON: {"label": "...", "confidence": 0-1, "rationale": "<=25 words"}."""


@dataclass
class LabelResult:
    label: str
    confidence: float
    rationale: str
    stable: bool
    latency_s: float


class OpenAILabeler:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def _one(self, text: str, temperature: float) -> tuple[str, float, str]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=120,
        )
        data = json.loads(resp.choices[0].message.content)
        label = str(data.get("label", "neutral")).strip().lower()
        if label not in ("bullish", "bearish", "neutral"):
            label = "neutral"
        conf = float(data.get("confidence", 0.5) or 0.5)
        return label, conf, str(data.get("rationale", ""))[:200]

    def label(self, text: str) -> LabelResult:
        t0 = time.perf_counter()
        a_label, a_conf, a_rat = self._one(text, 0.0)
        b_label, _, _ = self._one(text, 0.5)
        return LabelResult(
            label=a_label,
            confidence=a_conf,
            rationale=a_rat,
            stable=(a_label == b_label),
            latency_s=time.perf_counter() - t0,
        )
