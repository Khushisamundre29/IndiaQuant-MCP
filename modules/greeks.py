import math


def _norm_cdf(x: float) -> float:
    """
    Standard normal cumulative distribution function.
    Uses an Abramowitz & Stegun approximation.
    """
    a1 = 0.319381530
    a2 = -0.356563782
    a3 = 1.781477937
    a4 = -1.821255978
    a5 = 1.330274429

    if x >= 0:
        t = 1.0 / (1.0 + 0.2316419 * x)
        poly = t * (a1 + t * (a2 + t * (a3 + t * (a4 + t * a5))))
        return 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x) * poly
    else:
        return 1.0 - _norm_cdf(-x)


def _norm_pdf(x: float) -> float:
    """Standard normal probability density."""
    return (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x)


def calculate_greeks(
    spot: float,
    strike: float,
    time_years: float,
    risk_free: float,
    volatility: float,
    option_type: str,
) -> dict:
    """
    Black-Scholes pricing with Greeks.
    """
    if time_years <= 0:
        intrinsic = max(0, spot - strike) if option_type == "CE" else max(0, strike - spot)
        return {
            "error": "Option has expired",
            "intrinsic_value": round(intrinsic, 2),
        }

    if volatility <= 0:
        return {"error": "Volatility must be positive"}

    if spot <= 0 or strike <= 0:
        return {"error": "Spot and strike must be positive"}

    d1 = (
        math.log(spot / strike) + (risk_free + 0.5 * volatility ** 2) * time_years
    ) / (volatility * math.sqrt(time_years))

    d2 = d1 - volatility * math.sqrt(time_years)

    discount = math.exp(-risk_free * time_years)

    Nd1 = _norm_cdf(d1)
    Nd2 = _norm_cdf(d2)
    Nnd1 = _norm_cdf(-d1)
    Nnd2 = _norm_cdf(-d2)
    nd1 = _norm_pdf(d1)

    if option_type == "CE":
        price = spot * Nd1 - strike * discount * Nd2
        delta = Nd1
        theta = (
            -(spot * nd1 * volatility) / (2 * math.sqrt(time_years))
            - risk_free * strike * discount * Nd2
        ) / 365
        rho = strike * time_years * discount * Nd2 / 100

    else:
        price = strike * discount * Nnd2 - spot * Nnd1
        delta = Nd1 - 1
        theta = (
            -(spot * nd1 * volatility) / (2 * math.sqrt(time_years))
            + risk_free * strike * discount * Nnd2
        ) / 365
        rho = -strike * time_years * discount * Nnd2 / 100

    gamma = nd1 / (spot * volatility * math.sqrt(time_years))
    vega = spot * nd1 * math.sqrt(time_years) / 100

    if option_type == "CE":
        intrinsic = max(0, spot - strike)
    else:
        intrinsic = max(0, strike - spot)

    time_value = max(0, price - intrinsic)

    diff_pct = abs(spot - strike) / spot
    if diff_pct < 0.005:
        moneyness = "ATM"
    elif (option_type == "CE" and spot > strike) or (option_type == "PE" and spot < strike):
        moneyness = "ITM"
    else:
        moneyness = "OTM"

    return {
        "theoretical_price": round(price, 2),
        "intrinsic_value": round(intrinsic, 2),
        "time_value": round(time_value, 2),
        "moneyness": moneyness,
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4),
        "d1": round(d1, 4),
        "d2": round(d2, 4),
    }


def solve_implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_years: float,
    risk_free: float,
    option_type: str,
    tolerance: float = 1e-5,
    max_iter: int = 100,
) -> float:
    """
    Estimate implied volatility using bisection.
    """
    if market_price <= 0 or time_years <= 0:
        return 0.0

    low, high = 0.001, 5.0

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        result = calculate_greeks(spot, strike, time_years, risk_free, mid, option_type)

        if "error" in result:
            return 0.0

        bs_price = result["theoretical_price"]
        diff = bs_price - market_price

        if abs(diff) < tolerance:
            return round(mid, 4)

        if diff < 0:
            low = mid
        else:
            high = mid

    return round((low + high) / 2, 4)