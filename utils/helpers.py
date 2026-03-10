from datetime import datetime


def format_symbol(symbol: str) -> str:
    """
    yfinance needs NSE stocks to end with .NS
    So if someone types "RELIANCE" we convert it to "RELIANCE.NS"
    Index symbols like ^NSEI are left alone.
    """
    symbol = symbol.upper().strip()

    # already has an exchange suffix or is an index
    if symbol.startswith("^") or "." in symbol:
        return symbol

    return f"{symbol}.NS"


def round2(value) -> float:
    """Just a shortcut so we don't write round(..., 2) everywhere."""
    if value is None:
        return None
    return round(float(value), 2)


def pct_change(new_val: float, old_val: float) -> float:
    """Calculate percentage change between two values."""
    if old_val == 0:
        return 0.0
    return round((new_val - old_val) / old_val * 100, 2)


def get_market_status() -> str:
    """
    Check if NSE is currently open.
    NSE runs Mon-Fri, 9:15 AM to 3:30 PM IST.
    Note: this uses the server's local time, so deploy in IST timezone.
    """
    now = datetime.now()
    weekday = now.weekday()  # 0 = Monday, 6 = Sunday

    if weekday >= 5:
        return "CLOSED (Weekend)"

    time_in_minutes = now.hour * 60 + now.minute

    market_open  = 9  * 60 + 15   # 555 minutes from midnight
    market_close = 15 * 60 + 30   # 930 minutes from midnight

    if time_in_minutes < market_open:
        return "PRE-OPEN"
    elif time_in_minutes <= market_close:
        return "OPEN"
    else:
        return "CLOSED (After Hours)"


def years_until(expiry_str: str) -> float:
    """
    Given an expiry date string like "2025-01-30",
    return how many years remain from today.
    Used in Black-Scholes (T parameter).
    """
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except ValueError:
        # sometimes yfinance gives us "2025-01-30 00:00:00"
        expiry = datetime.fromisoformat(expiry_str).date()

    today = datetime.now().date()
    days_left = (expiry - today).days
    return max(days_left / 365.0, 0.0)  # never return negative


def make_error(message: str, symbol: str = "") -> dict:
    """Standard error response so all tools fail the same way."""
    return {
        "status": "error",
        "message": message,
        "symbol": symbol,
    }