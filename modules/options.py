import yfinance as yf
from utils.helpers import format_symbol, round2, years_until, make_error
from modules.greeks import calculate_greeks, solve_implied_volatility
from config.settings import RISK_FREE_RATE


def get_options_chain(symbol: str, expiry: str = "") -> dict:
    """
    Fetch full options chain (calls + puts) for a symbol.
    Enriches each row with Black-Scholes Greeks.
    Also calculates max pain and PCR.
    """
    sym = format_symbol(symbol)

    try:
        ticker = yf.Ticker(sym)

        # get list of available expiry dates
        available = ticker.options
        if not available:
            return make_error(f"No options data found for {sym}", sym)

        # use provided expiry or default to nearest
        chosen = expiry if expiry in available else available[0]

        chain = ticker.option_chain(chosen)
        calls_df = chain.calls
        puts_df  = chain.puts

        # get spot price
        fi    = ticker.fast_info
        spot  = getattr(fi, "last_price", None)
        if spot is None:
            hist  = ticker.history(period="1d")
            spot  = float(hist["Close"].iloc[-1]) if not hist.empty else None
        if spot is None:
            return make_error("Could not fetch spot price", sym)

        T = years_until(chosen)   # time to expiry in years

        calls_data = _enrich_with_greeks(calls_df, spot, T, "CE")
        puts_data  = _enrich_with_greeks(puts_df,  spot, T, "PE")

        total_call_oi = int(calls_df["openInterest"].fillna(0).sum())
        total_put_oi  = int(puts_df["openInterest"].fillna(0).sum())
        pcr = round(total_put_oi / max(total_call_oi, 1), 2)

        max_pain = _calculate_max_pain(calls_df, puts_df)

        return {
            "symbol":            sym,
            "spot":              round2(spot),
            "expiry":            chosen,
            "available_expiries": list(available[:5]),
            "days_to_expiry":    round(T * 365),
            "max_pain":          max_pain,
            "pcr":               pcr,
            "pcr_signal": (
                "BULLISH" if pcr > 1.2
                else "BEARISH" if pcr < 0.8
                else "NEUTRAL"
            ),
            "total_call_oi":     total_call_oi,
            "total_put_oi":      total_put_oi,
            "calls": calls_data[:15],   # show 15 strikes around ATM
            "puts":  puts_data[:15],
        }

    except Exception as e:
        return make_error(str(e), sym)


def _enrich_with_greeks(df, spot: float, T: float, option_type: str) -> list:
    """Add Greeks to each option row from the dataframe."""
    result = []

    for _, row in df.iterrows():
        strike = float(row.get("strike", 0))
        ltp    = float(row.get("lastPrice", 0))
        oi     = int(row.get("openInterest", 0) or 0)
        vol    = int(row.get("volume", 0) or 0)

        # yfinance gives us IV as a decimal (0.30 = 30%)
        iv = float(row.get("impliedVolatility", 0.25) or 0.25)

        greeks = calculate_greeks(spot, strike, T, RISK_FREE_RATE, iv, option_type)

        result.append({
            "strike":       strike,
            "type":         option_type,
            "ltp":          round2(ltp),
            "oi":           oi,
            "volume":       vol,
            "iv_pct":       round(iv * 100, 1),
            "moneyness":    greeks.get("moneyness"),
            "delta":        greeks.get("delta"),
            "gamma":        greeks.get("gamma"),
            "theta":        greeks.get("theta"),
            "vega":         greeks.get("vega"),
        })

    # sort by strike so it reads like a real options chain
    result.sort(key=lambda x: x["strike"])
    return result


def _calculate_max_pain(calls_df, puts_df) -> float:
    """
    Max pain = the strike price where the most option buyers lose money.
    (Option sellers profit most at this price at expiry.)

    Logic: for each possible expiry strike price,
    calculate total payout if market closes there.
    The strike with minimum total payout = max pain.
    """
    all_strikes = sorted(set(
        list(calls_df["strike"].dropna()) +
        list(puts_df["strike"].dropna())
    ))

    if not all_strikes:
        return 0.0

    min_pain = float("inf")
    max_pain_strike = all_strikes[0]

    for test_strike in all_strikes:
        # what would call holders receive if market closes at test_strike?
        call_pain = sum(
            float(row["openInterest"] or 0) * max(0, test_strike - row["strike"])
            for _, row in calls_df.iterrows()
        )
        # what would put holders receive?
        put_pain = sum(
            float(row["openInterest"] or 0) * max(0, row["strike"] - test_strike)
            for _, row in puts_df.iterrows()
        )

        total = call_pain + put_pain
        if total < min_pain:
            min_pain = total
            max_pain_strike = test_strike

    return round(max_pain_strike, 0)


def detect_unusual_activity(symbol: str, threshold: float = 2.0) -> dict:
    """
    Look for options where today's volume is unusually high vs open interest.
    High volume / OI ratio = someone is making a big directional bet today.
    """
    sym = format_symbol(symbol)

    try:
        ticker = yf.Ticker(sym)
        expiries = ticker.options
        if not expiries:
            return make_error("No options data", sym)

        alerts = []

        # check nearest 2 expiries
        for exp in expiries[:2]:
            chain = ticker.option_chain(exp)

            for opt_type, df in [("CE", chain.calls), ("PE", chain.puts)]:
                for _, row in df.iterrows():
                    oi  = float(row.get("openInterest", 0) or 0)
                    vol = float(row.get("volume", 0) or 0)

                    if oi == 0 or vol == 0:
                        continue

                    ratio = vol / oi

                    if ratio >= threshold:
                        severity = "HIGH" if ratio >= 5 else "MEDIUM"
                        alerts.append({
                            "expiry":      exp,
                            "type":        opt_type,
                            "strike":      float(row["strike"]),
                            "volume":      int(vol),
                            "open_interest": int(oi),
                            "vol_oi_ratio": round(ratio, 2),
                            "ltp":         round2(row.get("lastPrice", 0)),
                            "severity":    severity,
                            "note": (
                                f"{opt_type} {row['strike']} — "
                                f"volume is {round(ratio,1)}x open interest. "
                                f"Unusual intraday activity."
                            ),
                        })

        # sort: highest ratio first
        alerts.sort(key=lambda x: x["vol_oi_ratio"], reverse=True)

        return {
            "symbol":       sym,
            "total_alerts": len(alerts),
            "threshold_used": threshold,
            "alerts":       alerts[:10],   # top 10 is enough
        }

    except Exception as e:
        return make_error(str(e), sym)