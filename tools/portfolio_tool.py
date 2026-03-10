import yfinance as yf
from database import portfolio_db
from utils.helpers import format_symbol, round2, make_error


def run_pnl(portfolio_id: str = "default") -> dict:
    """
    MCP Tool: get_portfolio_pnl
    Fetches live prices for every position and calculates unrealized P&L.
    Also flags any stop-loss or target breaches.
    """
    portfolio = portfolio_db.get_portfolio(portfolio_id)
    if not portfolio:
        return make_error(f"Portfolio '{portfolio_id}' not found")

    positions = portfolio_db.get_positions(portfolio_id)
    cash = portfolio["cash_balance"]

    if not positions:
        return {
            "portfolio_id":    portfolio_id,
            "cash":            round2(cash),
            "invested":        0,
            "current_value":   0,
            "total_pnl":       0,
            "total_pnl_pct":   0,
            "positions":       [],
            "total_portfolio": round2(cash),
        }

    total_invested = 0.0
    total_current  = 0.0
    enriched = []

    for pos in positions:
        sym   = pos["symbol"]
        qty   = pos["quantity"]
        avg_p = pos["avg_price"]

        # fetch live price for this stock
        try:
            ticker = yf.Ticker(sym)
            fi = ticker.fast_info
            live_price = getattr(fi, "last_price", None)
            if live_price is None:
                hist = ticker.history(period="1d")
                live_price = float(hist["Close"].iloc[-1]) if not hist.empty else avg_p
        except Exception:
            live_price = avg_p  # fall back to avg price if fetch fails

        invested = qty * avg_p
        current  = qty * float(live_price)
        pnl      = current - invested
        pnl_pct  = round((pnl / invested) * 100, 2) if invested > 0 else 0

        # check stop-loss and target
        alerts = []
        if pos.get("stop_loss") and float(live_price) <= pos["stop_loss"]:
            alerts.append(f"⚠️ STOP LOSS HIT! SL={pos['stop_loss']} | LTP={round2(live_price)}")
        if pos.get("target") and float(live_price) >= pos["target"]:
            alerts.append(f"🎯 TARGET HIT! Target={pos['target']} | LTP={round2(live_price)}")

        # rough volatility-based risk score (1-10)
        try:
            hist_df = yf.download(sym, period="3mo", interval="1d",
                                  progress=False, auto_adjust=True)
            if not hist_df.empty:
                daily_returns = hist_df["Close"].pct_change().dropna()
                annual_vol = float(daily_returns.std() * (252 ** 0.5) * 100)
            else:
                annual_vol = 25.0
        except Exception:
            annual_vol = 25.0

        risk_score = round(min(10, annual_vol / 5), 1)

        total_invested += invested
        total_current  += current

        enriched.append({
            "symbol":        sym,
            "quantity":      qty,
            "avg_price":     round2(avg_p),
            "live_price":    round2(live_price),
            "invested":      round2(invested),
            "current_value": round2(current),
            "pnl":           round2(pnl),
            "pnl_pct":       pnl_pct,
            "stop_loss":     pos.get("stop_loss"),
            "target":        pos.get("target"),
            "risk_score":    risk_score,
            "annual_vol_pct": round(annual_vol, 1),
            "alerts":        alerts,
        })

    total_pnl     = total_current - total_invested
    total_pnl_pct = round((total_pnl / total_invested) * 100, 2) if total_invested > 0 else 0

    return {
        "portfolio_id":    portfolio_id,
        "cash":            round2(cash),
        "invested":        round2(total_invested),
        "current_value":   round2(total_current),
        "total_pnl":       round2(total_pnl),
        "total_pnl_pct":   total_pnl_pct,
        "total_portfolio": round2(cash + total_current),
        "positions":       sorted(enriched, key=lambda x: x["pnl"], reverse=True),
    }


def run_trade(
    symbol:       str,
    quantity:     int,
    side:         str,
    portfolio_id: str   = "default",
    stop_loss:    float = None,
    target:       float = None,
) -> dict:
    """
    MCP Tool: place_virtual_trade
    Executes a paper trade at the current live price.
    """
    if not all([symbol, quantity, side]):
        return {"error": "symbol, quantity, side are required"}

    if quantity <= 0:
        return {"error": "quantity must be a positive integer"}

    side = side.upper()
    if side not in ("BUY", "SELL"):
        return {"error": "side must be BUY or SELL"}

    sym = format_symbol(symbol)

    # fetch live execution price
    try:
        ticker = yf.Ticker(sym)
        fi = ticker.fast_info
        price = getattr(fi, "last_price", None)
        if price is None:
            hist = ticker.history(period="1d")
            if hist.empty:
                return make_error(f"Cannot fetch price for {sym}")
            price = float(hist["Close"].iloc[-1])
    except Exception as e:
        return make_error(str(e), sym)

    if side == "BUY":
        result = portfolio_db.execute_buy(
            portfolio_id, sym, quantity, float(price), stop_loss, target
        )
        if "error" not in result:
            result["message"] = (
                f"Bought {quantity} shares of {sym} @ ₹{price:.2f}. "
                f"Total: ₹{quantity * price:,.0f}"
            )
    else:
        result = portfolio_db.execute_sell(portfolio_id, sym, quantity, float(price))
        if "error" not in result:
            pnl = result.get("realized_pnl", 0)
            result["message"] = (
                f"Sold {quantity} shares of {sym} @ ₹{price:.2f}. "
                f"Realized P&L: ₹{pnl:+,.2f}"
            )

    return result