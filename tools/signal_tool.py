from modules.market_data import get_ohlc_history
from modules.indicators import compute_signal_score, score_to_signal
from modules.sentiment import fetch_sentiment
from utils.helpers import format_symbol, make_error


def run(symbol: str, timeframe: str = "1d") -> dict:
    """
    MCP Tool: generate_signal
    Combines RSI, MACD, Bollinger Bands + news sentiment
    into a single BUY / SELL / HOLD signal with confidence %.
    """
    if not symbol:
        return {"error": "symbol is required"}

    sym = format_symbol(symbol)

    # map MCP timeframe param to yfinance period + interval
    period_map = {
        "1d":  ("6mo",  "1d"),
        "1wk": ("2y",   "1wk"),
        "1mo": ("5y",   "1mo"),
    }
    period, interval = period_map.get(timeframe, ("6mo", "1d"))

    # ── fetch price history ──────────────────────────────────────────
    try:
        df = get_ohlc_history(sym, period=period, interval=interval)
    except Exception as e:
        return make_error(str(e), sym)

    if len(df) < 30:
        return make_error("Not enough data (need at least 30 bars)", sym)

    # ── technical analysis ───────────────────────────────────────────
    tech = compute_signal_score(df)

    # ── sentiment ────────────────────────────────────────────────────
    sentiment = fetch_sentiment(symbol)
    sent_score = sentiment.get("sentiment_score", 0.0)

    # ── combine into final signal ────────────────────────────────────
    final = score_to_signal(tech["composite_score"], sent_score)

    # ── support / resistance from recent swings ──────────────────────
    recent_50 = df.tail(50)
    support    = round(float(recent_50["Low"].min()), 2)
    resistance = round(float(recent_50["High"].max()), 2)

    current_price = tech["current_price"]

    return {
        "symbol":    sym,
        "timeframe": timeframe,
        "signal":    final["signal"],
        "confidence": final["confidence"],
        "score":     final["score"],
        "price":     current_price,
        "levels": {
            "support":    support,
            "resistance": resistance,
        },
        "indicators": {
            "rsi":          tech["rsi"],
            "macd":         tech["macd"],
            "macd_signal":  tech["macd_signal"],
            "macd_hist":    tech["macd_hist"],
            "bb_upper":     tech["bb_upper"],
            "bb_lower":     tech["bb_lower"],
            "ema20":        tech["ema20"],
            "ema50":        tech["ema50"],
            "volume_ratio": tech["volume_ratio"],
        },
        "sentiment": {
            "score":   sentiment.get("sentiment_score"),
            "signal":  sentiment.get("signal"),
            "articles": sentiment.get("total_articles"),
        },
        "summary": _build_summary(final["signal"], current_price, support, resistance, final["confidence"]),
    }


def _build_summary(signal, price, support, resistance, confidence) -> str:
    if signal == "BUY":
        return (
            f"BUY near ₹{price:.0f}. "
            f"Stop loss: ₹{round(support * 0.99, 0):.0f}. "
            f"Target: ₹{round(resistance * 0.99, 0):.0f}. "
            f"Confidence: {confidence:.0f}%."
        )
    elif signal == "SELL":
        return (
            f"SELL at ₹{price:.0f}. "
            f"Next support around ₹{support:.0f}. "
            f"Confidence: {confidence:.0f}%."
        )
    else:
        return (
            f"HOLD. Wait for a breakout above ₹{resistance:.0f} "
            f"or breakdown below ₹{support:.0f}. "
            f"Confidence: {confidence:.0f}%."
        )