from modules.market_data import get_live_price


def run(symbol: str) -> dict:
    """
    MCP Tool: get_live_price
    Returns current price, change%, volume for any NSE/BSE stock or index.
    """
    if not symbol:
        return {"error": "symbol is required"}

    return get_live_price(symbol)