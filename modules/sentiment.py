import os
import re
import requests
from datetime import datetime, timedelta
from config.settings import NEWS_API_KEY, ALPHA_VANTAGE_KEY


# ── Sentiment word lists ─────────────────────────────────────────────
# Simple approach: count positive/negative finance words in headlines.
# Not perfect but works without any paid NLP library.

POSITIVE_WORDS = {
    "surge", "rally", "soar", "gain", "rise", "jump", "climb", "strong",
    "beat", "record", "high", "growth", "profit", "upgrade", "breakout",
    "recovery", "expansion", "bullish", "outperform", "acquisition",
    "dividend", "launch", "win", "positive", "confident", "robust",
}

NEGATIVE_WORDS = {
    "crash", "fall", "drop", "decline", "tumble", "plunge", "loss", "weak",
    "miss", "low", "risk", "warning", "downgrade", "breakdown", "fraud",
    "probe", "default", "debt", "layoff", "cut", "delay", "fine", "penalty",
    "lawsuit", "bearish", "underperform", "negative", "concern", "crisis",
}

NEGATORS = {"not", "no", "never", "fails", "without", "unable", "despite"}


def _score_text(text: str) -> float:
    """
    Very simple lexicon scorer.
    Returns a value between -1.0 (very negative) and +1.0 (very positive).
    """
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    score = 0.0

    for i, word in enumerate(words):
        prev = words[i - 1] if i > 0 else ""
        flip = -1 if prev in NEGATORS else 1

        if word in POSITIVE_WORDS:
            score += 0.3 * flip
        elif word in NEGATIVE_WORDS:
            score += -0.3 * flip

    # clamp to [-1, 1]
    return max(-1.0, min(1.0, score))


def fetch_sentiment(symbol: str) -> dict:
    """
    Fetch recent news for a stock and return a sentiment score.
    Tries NewsAPI first, falls back to Alpha Vantage.
    """
    # strip exchange suffix for search
    clean = symbol.replace(".NS", "").replace(".BO", "")

    headlines = []

    if NEWS_API_KEY:
        headlines = _from_newsapi(clean)
    
    if not headlines and ALPHA_VANTAGE_KEY and ALPHA_VANTAGE_KEY != "demo":
        headlines = _from_alpha_vantage(clean)

    if not headlines:
        return {
            "symbol":          symbol,
            "sentiment_score": 0.0,
            "signal":          "NEUTRAL",
            "total_articles":  0,
            "headlines":       [],
            "note": (
                "No news API key found. "
                "Add NEWS_API_KEY to .env for sentiment data."
            ),
        }

    # score each headline
    scores = []
    enriched = []

    for h in headlines:
        title = h.get("title", "")
        desc  = h.get("description", "")
        s     = _score_text(f"{title} {desc}")
        scores.append(s)
        enriched.append({
            "title":   title,
            "source":  h.get("source", ""),
            "date":    h.get("publishedAt", ""),
            "score":   round(s, 2),
        })

    avg = round(sum(scores) / len(scores), 3)

    signal = (
        "POSITIVE" if avg >= 0.15
        else "NEGATIVE" if avg <= -0.15
        else "NEUTRAL"
    )

    return {
        "symbol":          symbol,
        "sentiment_score": avg,
        "signal":          signal,
        "total_articles":  len(headlines),
        "headlines":       enriched[:8],
    }


def _from_newsapi(query: str) -> list:
    """NewsAPI.org — 100 requests/day free."""
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={query}"
        f"&from={since}"
        f"&sortBy=publishedAt"
        f"&language=en"
        f"&pageSize=20"
        f"&apiKey={NEWS_API_KEY}"
    )
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            articles = data.get("articles", [])
            # normalize source field
            for a in articles:
                if isinstance(a.get("source"), dict):
                    a["source"] = a["source"].get("name", "")
            return articles
    except Exception:
        pass
    return []


def _from_alpha_vantage(symbol: str) -> list:
    """Alpha Vantage news endpoint — 25 requests/day free."""
    url = (
        f"https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT"
        f"&tickers={symbol}"
        f"&limit=20"
        f"&apikey={ALPHA_VANTAGE_KEY}"
    )
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            feed = resp.json().get("feed", [])
            # map to the same format we use from newsapi
            return [
                {
                    "title":       a.get("title", ""),
                    "description": a.get("summary", ""),
                    "source":      a.get("source", ""),
                    "publishedAt": a.get("time_published", ""),
                }
                for a in feed
            ]
    except Exception:
        pass
    return []