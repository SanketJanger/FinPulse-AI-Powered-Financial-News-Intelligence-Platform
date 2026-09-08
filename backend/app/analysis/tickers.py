"""
Entity extraction: stock tickers + company names from an article's text.

Two complementary passes:
1. Regex — high precision. Cashtags ($AAPL) and exchange-qualified
   mentions ((NASDAQ: MSFT)).
2. spaCy NER (en_core_web_sm) — ORG entities become `companies`; any that
   match a small well-known map also contribute a ticker.

spaCy is loaded once, lazily. `extract_entities` is CPU-bound and sync —
call it via asyncio.to_thread from async code.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("finpulse.tickers")

_CASHTAG = re.compile(r"\$([A-Z]{1,5})(?:\.[A-Z])?\b")
_EXCHANGE = re.compile(
    r"\b(?:NYSE|NASDAQ|NYSEARCA|AMEX|OTC|LON|TSX)\s*:\s*([A-Z]{1,5})(?:\.[A-Z])?\b"
)

# Just enough to be useful on finance headlines; extend as needed.
_COMPANY_TO_TICKER = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "tesla": "TSLA",
    "netflix": "NFLX",
    "intel": "INTC",
    "amd": "AMD",
    "broadcom": "AVGO",
    "oracle": "ORCL",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "goldman sachs": "GS",
    "morgan stanley": "MS",
    "bank of america": "BAC",
    "wells fargo": "WFC",
    "citigroup": "C",
    "berkshire hathaway": "BRK.B",
    "exxon": "XOM",
    "exxon mobil": "XOM",
    "chevron": "CVX",
    "boeing": "BA",
    "walmart": "WMT",
    "disney": "DIS",
    "coinbase": "COIN",
    "palantir": "PLTR",
    "uber": "UBER",
    "ford": "F",
    "general motors": "GM",
    "unitedhealth": "UNH",
    "eli lilly": "LLY",
    "taiwan semiconductor": "TSM",
    "tsmc": "TSM",
}

# ORG entities that are noise for our purposes.
_ORG_STOPWORDS = {
    "reuters", "bloomberg", "cnbc", "the wall street journal", "wsj",
    "associated press", "ap", "the new york times", "yahoo finance",
    "fox business", "business insider", "fortune", "the fed", "fed",
    "federal reserve", "the federal reserve", "sec", "congress", "senate",
    "house", "white house", "eu", "european union",
}

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        _nlp = spacy.load("en_core_web_sm", disable=["lemmatizer", "textcat"])
    return _nlp


def _clean_org(text: str) -> str | None:
    text = re.sub(r"^(the|a|an)\s+", "", text.strip(), flags=re.I).strip(" .,'\"")
    if len(text) < 2 or text.lower() in _ORG_STOPWORDS:
        return None
    if not any(c.isalpha() for c in text):
        return None
    return text


def extract_entities(text: str) -> tuple[list[str], list[str]]:
    """Return (tickers, companies), each a sorted list of unique strings."""
    text = text or ""
    tickers: set[str] = set()
    companies: set[str] = set()

    for m in _CASHTAG.finditer(text):
        tickers.add(m.group(1))
    for m in _EXCHANGE.finditer(text):
        tickers.add(m.group(1))

    try:
        doc = _get_nlp()(text)
        for ent in doc.ents:
            if ent.label_ != "ORG":
                continue
            name = _clean_org(ent.text)
            if not name:
                continue
            companies.add(name)
            mapped = _COMPANY_TO_TICKER.get(name.lower())
            if mapped:
                tickers.add(mapped)
    except Exception:
        logger.exception("spaCy NER failed — returning regex tickers only")

    return sorted(tickers), sorted(companies)
