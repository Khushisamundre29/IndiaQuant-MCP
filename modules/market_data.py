import time
import yfinance as yf
from utils.helpers import format_symbol, round2, pct_change, get_market_status, make_error
from config.settings import CACHE_TTL_SECONDS, SECTOR_INDICES, ALL_NIFTY50

# simple in-memory cache: { symbol -> (data_dict, timestamp) }
_cache = {}


def _is_cache_fresh(symbol: str) -> bool:
    if symbol not in _cache:
        return False
    _, saved_at = _cache[symbol]
    return (time.time() - saved_at) < CACHE_TTL_SECONDS


def get_live_price(symbol: str) -> dict:
    """
    Fetch the latest price, change%, and volume for a stock or index.
    Results are cached for CACHE_TTL_SECONDS to avoid hammering yfinance.
    """
    sym = format_symbol(symbol)

    # return cached result if still fresh
    if _is_cache_fresh(sym):
        data, _ = _cache[sym]
        data["cached"] = True
        return data

    try:
        ticker = yf.Ticker(sym)

        # fast_info is quicker than .info (which loads everything)
        fi = ticker.fast_info

        price = getattr(fi, "last_price", None)
        prev_close = getattr(fi, "previous_close", None)

        # if fast_info gave nothing, fall back to recent history
        if price is None:
            hist = ticker.history(period="5d", interval="1d")
            if hist.empty:
                return make_error(f"No data found for {sym}", sym)
            price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price

        change     = round2(price - prev_close) if prev_close else 0
        change_pct = pct_change(price, prev_close) if prev_close else 0

        # get today's volume from 1-min bars
        intraday = ticker.history(period="1d", interval="1m")
        volume = int(intraday["Volume"].sum()) if not intraday.empty else 0

        result = {
            "symbol":      sym,
            "price":       round2(price),
            "prev_close":  round2(prev_close),
            "change":      change,
            "change_pct":  change_pct,
            "volume":      volume,
            "day_high":    round2(getattr(fi, "day_high", None)),
            "day_low":     round2(getattr(fi, "day_low", None)),
            "52w_high":    round2(getattr(fi, "year_high", None)),
            "52w_low":     round2(getattr(fi, "year_low", None)),
            "market_status": get_market_status(),
            "cached":      False,
        }

        _cache[sym] = (result, time.time())
        return result

    except Exception as e:
        return make_error(str(e), sym)


def get_ohlc_history(symbol: str, period: str = "6mo", interval: str = "1d"):
    """
    Returns a pandas DataFrame with OHLCV columns.
    Used internally by the indicators module.
    period can be: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
    interval can be: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo
    """
    sym = format_symbol(symbol)
    df = yf.download(sym, period=period, interval=interval,
                     progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No OHLC data returned for {sym}")

    # yfinance sometimes returns multi-level columns — flatten them
    if isinstance(df.columns, object) and hasattr(df.columns, "droplevel"):
        try:
            df.columns = df.columns.droplevel(1)
        except Exception:
            pass

    return df


def get_sector_heatmap() -> dict:
    """
    Fetch % change for each major NSE sector index.
    Returns a dict you can read like a heatmap.
    """
    results = {}

    for sector_name, index_symbol in SECTOR_INDICES.items():
        try:
            ticker = yf.Ticker(index_symbol)
            hist = ticker.history(period="2d", interval="1d")

            if len(hist) >= 2:
                today_close = float(hist["Close"].iloc[-1])
                prev_close  = float(hist["Close"].iloc[-2])
                chg = pct_change(today_close, prev_close)
            elif len(hist) == 1:
                today_close = float(hist["Close"].iloc[-1])
                chg = 0.0
            else:
                results[sector_name] = {"error": "No data"}
                continue

            results[sector_name] = {
                "index":      index_symbol,
                "price":      round2(today_close),
                "change_pct": chg,
                # simple visual indicator
                "trend": "▲" if chg > 0 else ("▼" if chg < 0 else "—"),
            }

        except Exception as e:
            results[sector_name] = {"error": str(e)}

    return {
        "sectors":       results,
        "market_status": get_market_status(),
    }