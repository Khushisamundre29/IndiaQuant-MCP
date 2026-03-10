from modules.options import get_options_chain, detect_unusual_activity
from modules.greeks import calculate_greeks
from modules.market_data import get_live_price
from utils.helpers import years_until, make_error
from config.settings import RISK_FREE_RATE


def run_options_chain(symbol: str, expiry: str = "") -> dict:
    """
    MCP Tool: get_options_chain
    Returns CE + PE strikes with OI, volume, IV, and Greeks.
    """
    if not symbol:
        return {"error": "symbol is required"}
    return get_options_chain(symbol, expiry)


def run_greeks(
    symbol:      str,
    strike:      float,
    expiry:      str,
    option_type: str,
    iv:          float = 0.0,
) -> dict:
    """
    MCP Tool: calculate_greeks
    Runs our Black-Scholes implementation and returns
    Delta, Gamma, Theta, Vega for the given contract.
    """
    if not all([symbol, strike, expiry, option_type]):
        return {"error": "symbol, strike, expiry, option_type are all required"}

    option_type = option_type.upper()
    if option_type not in ("CE", "PE"):
        return {"error": "option_type must be CE or PE"}

    # get live spot price
    price_data = get_live_price(symbol)
    if "error" in price_data:
        return price_data

    spot = price_data["price"]
    T    = years_until(expiry)

    # if IV not given, try to get it from the options chain
    if iv <= 0:
        chain = get_options_chain(symbol, expiry)
        if "error" not in chain:
            opt_list = chain.get("calls" if option_type == "CE" else "puts", [])
            for opt in opt_list:
                if abs(opt["strike"] - strike) < 1:
                    iv = opt.get("iv_pct", 25) / 100
                    break
        if iv <= 0:
            iv = 0.25  # default 25% IV if we still can't find it

    greeks = calculate_greeks(spot, strike, T, RISK_FREE_RATE, iv, option_type)

    return {
        "symbol":      symbol,
        "strike":      strike,
        "expiry":      expiry,
        "option_type": option_type,
        "spot":        spot,
        "days_left":   round(T * 365),
        "iv_used_pct": round(iv * 100, 1),
        "greeks":      greeks,
        "plain_english": {
            "delta": f"For every ₹1 move in {symbol}, this option moves ₹{greeks.get('delta', 0):.2f}",
            "theta": f"This option loses ₹{abs(greeks.get('theta', 0)):.2f} per day from time decay",
            "vega":  f"A 1% rise in IV adds ₹{greeks.get('vega', 0):.2f} to option value",
            "gamma": f"Delta itself changes by {greeks.get('gamma', 0):.4f} per ₹1 move in stock",
        },
    }


def run_unusual_activity(symbol: str, threshold: float = 2.0) -> dict:
    """
    MCP Tool: detect_unusual_activity
    Finds options with abnormally high volume vs open interest.
    """
    if not symbol:
        return {"error": "symbol is required"}
    return detect_unusual_activity(symbol, threshold)