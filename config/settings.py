import os
from dotenv import load_dotenv

load_dotenv()

# API keys loaded from environment variables
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")

# Cache duration for price data
CACHE_TTL_SECONDS = 20

# Risk-free rate used in Black-Scholes calculations
RISK_FREE_RATE = 0.065

# Initial capital for the virtual portfolio
STARTING_CASH = 1_000_000

# Nifty 50 symbols grouped by sector
NIFTY50_BY_SECTOR = {
    "IT": [
        "TCS.NS", "INFY.NS", "WIPRO.NS",
        "HCLTECH.NS", "TECHM.NS",
    ],
    "Banking": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS",
        "AXISBANK.NS", "SBIN.NS", "INDUSINDBK.NS",
    ],
    "Auto": [
        "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS",
        "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
    ],
    "Pharma": [
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
    ],
    "FMCG": [
        "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS",
    ],
    "Energy": [
        "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS",
    ],
    "Metal": [
        "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS",
    ],
    "Finance": [
        "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    ],
}

# Flattened list of all symbols
ALL_NIFTY50 = [sym for syms in NIFTY50_BY_SECTOR.values() for sym in syms]

# Sector index symbols
SECTOR_INDICES = {
    "IT":      "^CNXIT",
    "Banking": "^NSEBANK",
    "Auto":    "^CNXAUTO",
    "Pharma":  "^CNXPHARMA",
    "FMCG":    "^CNXFMCG",
    "Energy":  "^CNXENERGY",
    "Metal":   "^CNXMETAL",
}

# NSE trading hours (IST)
MARKET_OPEN_HOUR   = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR  = 15
MARKET_CLOSE_MINUTE = 30