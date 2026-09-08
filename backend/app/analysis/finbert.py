"""
FinBERT sentiment model wrapper.

`FinBERTAnalyzer` owns the transformers model + tokenizer. It is loaded
*once* (call `.load()` at service startup) and then `.analyze()` is cheap
to call per article. Everything here is synchronous and CPU/GPU-bound —
callers in async code should hand it to `asyncio.to_thread`.

ProsusAI/finbert emits labels {positive, negative, neutral}; we surface
them as the finance-desk vocabulary {bullish, bearish, neutral}.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("finpulse.finbert")

# HF label -> our label
_LABEL_MAP = {"positive": "bullish", "negative": "bearish", "neutral": "neutral"}

_MAX_TOKENS = 512


class AnalyzerUnavailable(RuntimeError):
    """Raised when analyze() is called but the model never loaded."""


@dataclass(frozen=True)
class SentimentResult:
    label: str  # "bullish" | "bearish" | "neutral"
    confidence: float  # softmax probability of `label`, 0..1
    scores: dict[str, float]  # full distribution over our labels


class FinBERTAnalyzer:
    def __init__(self, model_name: str = "ProsusAI/finbert", device: str | None = None):
        self.model_name = model_name
        self._requested_device = device
        self.device: str | None = None
        self._tokenizer = None
        self._model = None
        self._torch = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def load(self) -> None:
        """Import torch/transformers, pull the model (cached after first
        run), move it to GPU when one is present, and put it in eval mode.
        Safe to call more than once; a second call is a no-op."""
        if self._ready:
            return

        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.device = self._requested_device or ("cuda" if torch.cuda.is_available() else "cpu")

        logger.info("loading FinBERT '%s' onto %s ...", self.model_name, self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self._model.to(self.device)
        self._model.eval()
        self._ready = True
        logger.info("FinBERT ready (labels=%s)", self._model.config.id2label)

    def analyze(self, text: str) -> SentimentResult:
        if not self._ready:
            raise AnalyzerUnavailable("FinBERTAnalyzer.load() has not succeeded")

        torch = self._torch
        text = (text or "").strip()
        if not text:
            # Nothing to score — treat as neutral with no confidence.
            return SentimentResult("neutral", 0.0, {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0})

        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=_MAX_TOKENS,
            padding=False,
        ).to(self.device)

        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).squeeze(0).tolist()

        id2label = self._model.config.id2label
        scores: dict[str, float] = {}
        for idx, prob in enumerate(probs):
            our_label = _LABEL_MAP.get(id2label[idx].lower(), id2label[idx].lower())
            scores[our_label] = round(float(prob), 6)

        top_label = max(scores, key=scores.get)
        return SentimentResult(label=top_label, confidence=scores[top_label], scores=scores)
