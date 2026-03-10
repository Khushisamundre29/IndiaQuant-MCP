import pandas as pd
import numpy as np


# ── RSI ─────────────────────────────────────────────────────────────

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index.
    RSI = 100 - (100 / (1 + avg_gain / avg_loss))

    < 30  → oversold (possible buy)
    > 70  → overbought (possible sell)
    """
    delta = close.diff()

    gain = delta.clip(lower=0)   # keep only positive moves
    loss = -delta.clip(upper=0)  # keep only negative moves (make positive)

    # exponential moving average of gains and losses
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs  = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ── MACD ─────────────────────────────────────────────────────────────

def compute_macd(close: pd.Series, fast=12, slow=26, signal=9):
    """
    MACD = EMA(12) - EMA(26)
    Signal line = EMA(9) of MACD
    Histogram = MACD - Signal

    When MACD crosses above signal → bullish
    When MACD crosses below signal → bearish
    """
    ema_fast   = close.ewm(span=fast,   adjust=False).mean()
    ema_slow   = close.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line

    return macd_line, signal_line, histogram


# ── Bollinger Bands ──────────────────────────────────────────────────

def compute_bollinger_bands(close: pd.Series, period=20, std_devs=2.0):
    """
    Middle band = 20-day SMA
    Upper band  = Middle + 2 * std dev
    Lower band  = Middle - 2 * std dev

    Price touching lower band → oversold
    Price touching upper band → overbought
    """
    middle = close.rolling(window=period).mean()
    std    = close.rolling(window=period).std()
    upper  = middle + std_devs * std
    lower  = middle - std_devs * std

    return upper, middle, lower


# ── EMA ──────────────────────────────────────────────────────────────

def compute_ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


# ── Signal Score ─────────────────────────────────────────────────────

def compute_signal_score(df: pd.DataFrame) -> dict:
    """
    Takes OHLCV dataframe, runs all indicators,
    and returns a score from -100 to +100.

    Positive = bullish, Negative = bearish.
    We also return each indicator's value so Claude can explain it.
    """
    close  = df["Close"]
    volume = df["Volume"]

    # ── compute everything ──
    rsi_series                     = compute_rsi(close)
    macd_line, signal_line, hist   = compute_macd(close)
    upper_bb, mid_bb, lower_bb     = compute_bollinger_bands(close)
    ema20 = compute_ema(close, 20)
    ema50 = compute_ema(close, 50)

    # latest values
    rsi       = float(rsi_series.iloc[-1])
    macd_val  = float(macd_line.iloc[-1])
    sig_val   = float(signal_line.iloc[-1])
    hist_val  = float(hist.iloc[-1])
    curr      = float(close.iloc[-1])
    upper     = float(upper_bb.iloc[-1])
    lower_b   = float(lower_bb.iloc[-1])
    mid       = float(mid_bb.iloc[-1])
    e20       = float(ema20.iloc[-1])
    e50       = float(ema50.iloc[-1]) if len(close) >= 50 else e20

    # volume ratio vs 20-day average
    vol_avg   = float(volume.rolling(20).mean().iloc[-1])
    vol_now   = float(volume.iloc[-1])
    vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 1.0

    # ── score each indicator on a simple scale ──

    # RSI: oversold gives +points, overbought gives -points
    if rsi < 30:
        rsi_score = 70
    elif rsi < 45:
        rsi_score = 30
    elif rsi < 55:
        rsi_score = 0
    elif rsi < 70:
        rsi_score = -30
    else:
        rsi_score = -70

    # MACD: positive histogram and above signal → bullish
    if macd_val > sig_val and hist_val > 0:
        macd_score = 70 if hist_val > float(hist.iloc[-2]) else 40
    elif macd_val < sig_val and hist_val < 0:
        macd_score = -70 if hist_val < float(hist.iloc[-2]) else -40
    else:
        macd_score = 0

    # Bollinger: at lower band → oversold bounce likely
    if curr <= lower_b:
        bb_score = 70
    elif curr >= upper:
        bb_score = -70
    elif curr > mid:
        bb_score = 20
    else:
        bb_score = -20

    # EMA trend: above both EMAs → uptrend
    ema_score = 0
    if curr > e20:
        ema_score += 25
    if curr > e50:
        ema_score += 35
    ema_score -= 30  # normalize so neutral is 0

    # Volume: high volume confirms the move
    price_dir = 1 if curr > float(close.iloc[-2]) else -1
    vol_score = 30 * price_dir if vol_ratio > 1.5 else 0

    # ── weighted average ──
    weights = {
        "rsi":    0.25,
        "macd":   0.30,
        "bb":     0.20,
        "ema":    0.15,
        "volume": 0.10,
    }
    scores = {
        "rsi":    rsi_score,
        "macd":   macd_score,
        "bb":     bb_score,
        "ema":    ema_score,
        "volume": vol_score,
    }
    composite = sum(scores[k] * weights[k] for k in scores)
    composite = max(-100, min(100, composite))

    return {
        "composite_score": round(composite, 1),
        "rsi":        round(rsi, 1),
        "macd":       round(macd_val, 3),
        "macd_signal": round(sig_val, 3),
        "macd_hist":  round(hist_val, 3),
        "bb_upper":   round(upper, 2),
        "bb_lower":   round(lower_b, 2),
        "bb_mid":     round(mid, 2),
        "ema20":      round(e20, 2),
        "ema50":      round(e50, 2),
        "volume_ratio": vol_ratio,
        "current_price": round(curr, 2),
        "individual_scores": scores,
    }


def score_to_signal(tech_score: float, sentiment_score: float) -> dict:
    """
    Combine technical score (65% weight) and
    sentiment score (-1 to 1, 35% weight) into
    a final BUY / SELL / HOLD call with confidence %.
    """
    # normalize sentiment from [-1,1] to [-100,100]
    sent_normalized = sentiment_score * 100

    final = (tech_score * 0.65) + (sent_normalized * 0.35)
    confidence = min(abs(final), 100)

    if final >= 25:
        signal = "BUY"
    elif final <= -25:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "signal":     signal,
        "confidence": round(confidence, 1),
        "score":      round(final, 1),
    }