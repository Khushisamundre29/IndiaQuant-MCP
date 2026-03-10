"""
Tests for RSI, MACD, Bollinger Bands in modules/indicators.py

Run with: pytest tests/test_indicators.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from modules.indicators import (
    compute_rsi, compute_macd, compute_bollinger_bands,
    score_to_signal,
)


def _up_series(n=100):
    """Steadily rising prices."""
    return pd.Series([100 + i * 0.5 for i in range(n)])

def _down_series(n=100):
    """Steadily falling prices."""
    return pd.Series([200 - i * 0.5 for i in range(n)])

def _flat_series(n=100):
    return pd.Series([100.0] * n)


# ── RSI ───────────────────────────────────────────────────────────────

def test_rsi_range():
    # RSI must always be 0–100
    rsi = compute_rsi(_up_series())
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()

def test_rsi_high_in_uptrend():
    rsi = compute_rsi(_up_series())
    assert rsi.dropna().iloc[-1] > 60

def test_rsi_low_in_downtrend():
    rsi = compute_rsi(_down_series())
    assert rsi.dropna().iloc[-1] < 40


# ── MACD ──────────────────────────────────────────────────────────────

def test_macd_lengths():
    s = _up_series()
    macd, signal, hist = compute_macd(s)
    assert len(macd) == len(s)
    assert len(signal) == len(s)
    assert len(hist) == len(s)

def test_macd_positive_in_uptrend():
    macd, signal, hist = compute_macd(_up_series())
    # after a long uptrend, MACD should be above signal
    assert float(macd.dropna().iloc[-1]) > float(signal.dropna().iloc[-1])


# ── Bollinger Bands ───────────────────────────────────────────────────

def test_bb_ordering():
    # upper must always be >= middle >= lower
    upper, mid, lower = compute_bollinger_bands(_up_series())
    valid = ~(upper.isna() | mid.isna() | lower.isna())
    assert (upper[valid] >= mid[valid]).all()
    assert (mid[valid] >= lower[valid]).all()

def test_bb_width_expands_with_volatility():
    # noisy series should have wider bands than flat series
    noisy = pd.Series(np.random.randn(100) * 10 + 100)
    flat  = _flat_series()
    _, _, lower_noisy = compute_bollinger_bands(noisy)
    _, _, lower_flat  = compute_bollinger_bands(flat)
    upper_n, _, _ = compute_bollinger_bands(noisy)
    upper_f, _, _ = compute_bollinger_bands(flat)
    width_noisy = (upper_n - lower_noisy).dropna().mean()
    width_flat  = (upper_f - lower_flat).dropna().mean()
    assert width_noisy > width_flat


# ── Signal combiner ───────────────────────────────────────────────────

def test_buy_signal():
    result = score_to_signal(80, 0.8)
    assert result["signal"] == "BUY"

def test_sell_signal():
    result = score_to_signal(-80, -0.8)
    assert result["signal"] == "SELL"

def test_hold_signal():
    result = score_to_signal(5, 0.0)
    assert result["signal"] == "HOLD"

def test_confidence_range():
    for tech in [-100, -50, 0, 50, 100]:
        result = score_to_signal(tech, 0)
        assert 0 <= result["confidence"] <= 100