"""
Tests for the Black-Scholes implementation in modules/greeks.py

Run with: pytest tests/test_greeks.py -v
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.greeks import calculate_greeks, solve_implied_volatility, _norm_cdf


# ── N(x) tests ───────────────────────────────────────────────────────

def test_norm_cdf_at_zero():
    # N(0) must be exactly 0.5 (bell curve is symmetric)
    assert abs(_norm_cdf(0) - 0.5) < 1e-5

def test_norm_cdf_symmetry():
    # N(x) + N(-x) = 1 always
    for x in [-3, -1, 0, 1, 3]:
        assert abs(_norm_cdf(x) + _norm_cdf(-x) - 1.0) < 1e-6

def test_norm_cdf_extremes():
    assert _norm_cdf(10)  > 0.9999
    assert _norm_cdf(-10) < 0.0001


# ── Put-call parity ───────────────────────────────────────────────────

def test_put_call_parity():
    """
    C - P = S - K * e^(-rT)
    This must hold for any BS model implementation.
    If it fails, the math is wrong.
    """
    S, K, T, r, sigma = 100, 100, 1.0, 0.065, 0.25
    call = calculate_greeks(S, K, T, r, sigma, "CE")
    put  = calculate_greeks(S, K, T, r, sigma, "PE")

    lhs = call["theoretical_price"] - put["theoretical_price"]
    rhs = S - K * math.exp(-r * T)

    assert abs(lhs - rhs) < 0.01, f"Parity broken: {lhs:.4f} vs {rhs:.4f}"


# ── Delta bounds ──────────────────────────────────────────────────────

def test_call_delta_is_positive():
    result = calculate_greeks(100, 100, 0.5, 0.065, 0.25, "CE")
    assert result["delta"] > 0

def test_put_delta_is_negative():
    result = calculate_greeks(100, 100, 0.5, 0.065, 0.25, "PE")
    assert result["delta"] < 0

def test_deep_itm_call_delta_near_one():
    # deep in the money call moves almost 1:1 with stock
    result = calculate_greeks(200, 100, 0.5, 0.065, 0.20, "CE")
    assert result["delta"] > 0.95

def test_deep_otm_call_delta_near_zero():
    # deep out of money call barely moves
    result = calculate_greeks(50, 200, 0.5, 0.065, 0.20, "CE")
    assert result["delta"] < 0.05


# ── Greeks signs ──────────────────────────────────────────────────────

def test_gamma_always_positive():
    # gamma is always positive for both calls and puts
    call = calculate_greeks(100, 100, 0.5, 0.065, 0.20, "CE")
    put  = calculate_greeks(100, 100, 0.5, 0.065, 0.20, "PE")
    assert call["gamma"] > 0
    assert put["gamma"]  > 0

def test_theta_always_negative():
    # time decay always hurts option holders
    call = calculate_greeks(100, 100, 0.5, 0.065, 0.20, "CE")
    put  = calculate_greeks(100, 100, 0.5, 0.065, 0.20, "PE")
    assert call["theta"] < 0
    assert put["theta"]  < 0

def test_vega_always_positive():
    # higher volatility = higher option price, always
    call = calculate_greeks(100, 100, 0.5, 0.065, 0.20, "CE")
    assert call["vega"] > 0


# ── Moneyness labels ──────────────────────────────────────────────────

def test_moneyness_labels():
    itm = calculate_greeks(110, 100, 0.5, 0.065, 0.20, "CE")
    otm = calculate_greeks(90,  100, 0.5, 0.065, 0.20, "CE")
    assert itm["moneyness"] == "ITM"
    assert otm["moneyness"] == "OTM"


# ── Implied volatility roundtrip ──────────────────────────────────────

def test_iv_roundtrip():
    """
    If we feed a BS price back into IV solver, we should get the original IV.
    This confirms our bisection solver is correct.
    """
    S, K, T, r, sigma = 100, 105, 0.5, 0.065, 0.22
    bs = calculate_greeks(S, K, T, r, sigma, "CE")
    market_price = bs["theoretical_price"]

    recovered_iv = solve_implied_volatility(market_price, S, K, T, r, "CE")
    assert abs(recovered_iv - sigma) < 0.01, f"IV roundtrip failed: {recovered_iv:.4f} vs {sigma}"


# ── Edge cases ────────────────────────────────────────────────────────

def test_expired_option():
    result = calculate_greeks(110, 100, 0, 0.065, 0.25, "CE")
    assert "error" in result

def test_zero_volatility():
    result = calculate_greeks(100, 100, 0.5, 0.065, 0.0, "CE")
    assert "error" in result