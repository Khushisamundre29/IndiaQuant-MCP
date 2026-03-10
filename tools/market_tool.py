import yfinance as yf
from modules.market_data import get_ohlc_history, get_sector_heatmap
from modules.indicators import compute_signal_score
from modules.sentiment import fetch_sentiment
from config.settings import NIFTY50_BY_SECTOR, ALL_NIFTY50
from utils.helpers import make_error


# ── helpers ──────────────────────────────────────────────────────────

def _get_stock_metrics(symbol: str) -> dict | None:
    """
    Compute key indicators for one stock.
    Returns None if data is unavailable (e.g. market closed, bad symbol).
    """
    try:
        df = get_ohlc_history(symbol, period="1y", interval="1d")
        if len(df) < 30:
            return None

        score_data = compute_signal_score(df)
        close = df["Close"]

        high_52w = float(df["High"].rolling(252).max().iloc[-1])
        low_52w  = float(df["Low"].rolling(252).min().iloc[-1])
        curr     = score_data["current_price"]

        return {
            "symbol":           symbol,
            "price":            curr,
            "rsi":              score_data["rsi"],
            "macd_hist":        score_data["macd_hist"],
            "ema20":            score_data["ema20"],
            "ema50":            score_data["ema50"],
            "volume_ratio":     score_data["volume_ratio"],
            "above_ema20":      curr > score_data["ema20"],
            "above_ema50":      curr > score_data["ema50"],
            "pct_from_52h":     round((curr - high_52w) / high_52w * 100, 1),
            "pct_from_52l":     round((curr - low_52w)  / low_52w  * 100, 1),
        }
    except Exception:
        return None


# ── filter definitions ───────────────────────────────────────────────

FILTERS = {
    "oversold":     lambda m: m["rsi"] < 30,
    "overbought":   lambda m: m["rsi"] > 70,
    "bullish_macd": lambda m: m["macd_hist"] > 0,
    "bearish_macd": lambda m: m["macd_hist"] < 0,
    "near_52w_high": lambda m: m["pct_from_52h"] > -3,
    "near_52w_low":  lambda m: m["pct_from_52l"] < 5,
    "volume_surge":  lambda m: m["volume_ratio"] > 2.0,
    "momentum":      lambda m: m["above_ema20"] and m["above_ema50"] and m["rsi"] > 50,
}

SORT_KEYS = {
    "oversold":      lambda m: m["rsi"],
    "overbought":    lambda m: -m["rsi"],
    "bullish_macd":  lambda m: -m["macd_hist"],
    "bearish_macd":  lambda m: m["macd_hist"],
    "near_52w_high": lambda m: -m["pct_from_52h"],
    "near_52w_low":  lambda m: m["pct_from_52l"],
    "volume_surge":  lambda m: -m["volume_ratio"],
    "momentum":      lambda m: -m["rsi"],
}


# ── tools ────────────────────────────────────────────────────────────

def run_scan(filter_type: str, sector: str = "all", top_n: int = 10) -> dict:
    """
    MCP Tool: scan_market
    Scans Nifty 50 stocks and filters them by your criteria.
    """
    if filter_type not in FILTERS:
        return {
            "error": f"Unknown filter '{filter_type}'.",
            "valid_filters": list(FILTERS.keys()),
        }

    # pick which stocks to scan
    if sector == "all":
        symbols = ALL_NIFTY50
    else:
        symbols = NIFTY50_BY_SECTOR.get(sector, [])
        if not symbols:
            return {
                "error": f"Unknown sector '{sector}'.",
                "valid_sectors": list(NIFTY50_BY_SECTOR.keys()),
            }

    # collect metrics (sequential to avoid hitting yfinance rate limits)
    metrics = []
    for sym in symbols:
        m = _get_stock_metrics(sym)
        if m:
            metrics.append(m)

    # apply filter
    filtered  = [m for m in metrics if FILTERS[filter_type](m)]
    sort_key  = SORT_KEYS.get(filter_type, lambda m: 0)
    sorted_results = sorted(filtered, key=sort_key)[:top_n]

    return {
        "filter":   filter_type,
        "sector":   sector,
        "scanned":  len(metrics),
        "matched":  len(filtered),
        "results":  sorted_results,
    }


def run_heatmap() -> dict:
    """
    MCP Tool: get_sector_heatmap
    Returns % change for each NSE sector index.
    """
    return get_sector_heatmap()