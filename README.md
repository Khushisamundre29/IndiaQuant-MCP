# IndiaQuant MCP 4

A real-time Indian stock market AI assistant built with Model Context Protocol (MCP). Connects to Claude Desktop and gives it full NSE/BSE market intelligence plus virtual trading capabilities using 100% free APIs.

---

## What It Does

Without this MCP, Claude knows nothing about today's Nifty price or whether Reliance is trending up. With it, Claude becomes a fully equipped stock market assistant.

**Example questions you can ask Claude:**
- "Should I buy HDFC Bank right now?"
- "What's the max pain for Nifty this expiry?"
- "Scan for oversold IT stocks"
- "Show me my portfolio P&L"
- "Is there unusual options activity on Infosys today?"

---
## Features

• Real-time Indian stock market data (NSE/BSE)  
• Options chain analysis with Greeks calculation  
• AI-generated trading signals using technical indicators  
• News sentiment analysis for stocks  
• Sector heatmap and market scanner  
• Virtual paper trading portfolio  
• Portfolio P&L tracking  
• Seamless integration with Claude Desktop using MCP  

---

## Architecture

<img width="3353" height="1205" alt="image" src="https://github.com/user-attachments/assets/b5f28651-9cde-4d2b-bfb9-3c187bb31e42" />
Claude Desktop communicates with the MCP server, which processes requests through different analytics modules and fetches data from market APIs.
---

## Free API Stack

| Purpose | API | Limit |
|---------|-----|-------|
| Live NSE/BSE prices | yfinance (Yahoo Finance) | Unlimited, free |
| Historical OHLC data | yfinance | Full history, free |
| Options chain | yfinance options | Free, NSE supported |
| News & sentiment | NewsAPI.org | 100 req/day free |
| Macro indicators | Alpha Vantage | 25 req/day free |
| Technical indicators | pandas (custom) | Unlimited, open source |
| Greeks calculation | Custom Black-Scholes | No API needed |

---

## 10 MCP Tools

| Tool | Input | Output |
|------|-------|--------|
| `get_live_price` | symbol | price, change%, volume, 52w range |
| `get_options_chain` | symbol, expiry | CE/PE strikes, OI, IV, Greeks |
| `analyze_sentiment` | symbol | score -1 to +1, headlines, signal |
| `generate_signal` | symbol, timeframe | BUY/SELL/HOLD, confidence 0-100% |
| `get_portfolio_pnl` | portfolio_id | positions, P&L, risk scores |
| `place_virtual_trade` | symbol, qty, side | order_id, execution price |
| `calculate_greeks` | option contract | delta, gamma, theta, vega |
| `detect_unusual_activity` | symbol | vol/OI spikes, alerts |
| `scan_market` | filter, sector | matching symbols with scores |
| `get_sector_heatmap` | — | all sectors with % change |

---

## Setup

### Prerequisites
- Python 3.10+
- Claude Desktop app (https://claude.ai/download)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/Khushisamundre29/IndiaQuant-MCP.git
cd IndiaQuant-MCP

# 2. Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate.bat

# Activate (Mac/Linux)
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up API keys
cp .env.example .env
# Edit .env and add your keys
```

### Get free API keys
- **NewsAPI**: https://newsapi.org/register (100 req/day)
- **Alpha Vantage**: https://www.alphavantage.co/support/#api-key (25 req/day)

### Connect to Claude Desktop

Open `%APPDATA%\Claude\claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "indiaquant": {
      "command": "C:\\path\\to\\IndiaQuant-MCP\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\IndiaQuant-MCP\\server\\server.py"],
      "env": {
        "NEWS_API_KEY": "your_key",
        "ALPHA_VANTAGE_KEY": "your_key"
      }
    }
  }
}
```

Restart Claude Desktop. The server status will show **running** in Settings → Developer.

---

## Running Tests

```bash
pytest tests/ -v
```

35 tests covering Black-Scholes math, technical indicators, and portfolio logic — all passing.

---

## Key Design Decisions

**Black-Scholes from scratch** — Implemented in `modules/greeks.py` without any library. Used the Abramowitz & Stegun approximation for the normal CDF (error < 7.5e-8). For implied volatility, used bisection over Newton-Raphson — slower but guaranteed to converge even when vega approaches zero near expiry.

**Technical indicator weighting** — Signal score combines 5 indicators: MACD 30%, RSI 25%, Bollinger Bands 20%, EMA cross 15%, Volume 10%. Final signal = 65% technical + 35% news sentiment.

**Caching** — 20-second in-memory cache in `market_data.py` to avoid hammering yfinance on repeated requests.

**SQLite for portfolio** — Zero-config, persists across restarts. Easy to swap to PostgreSQL by changing the connection string.

**Async architecture** — All MCP tools are async. yfinance blocking calls wrapped in `run_in_executor` to avoid blocking the event loop.

---

## Trade-offs

| Decision | Trade-off |
|----------|-----------|
| yfinance free API | 15-min delay during market hours, no tick data |
| Lexicon sentiment | Simple and fast — no paid NLP model needed |
| Bisection for IV | Slower than Newton-Raphson but never fails |
| SQLite | Not multi-user, perfect for single user paper trading |
| In-memory cache | Resets on server restart, no Redis dependency |

---

## Example Output

**get_live_price:**
```json
{
  "symbol": "RELIANCE.NS",
  "price": 1408.80,
  "change": -9.80,
  "change_pct": -0.69,
  "volume": 17715807,
  "market_status": "CLOSED (After Hours)"
}
```

**generate_signal:**
```json
{
  "signal": "BUY",
  "confidence": 67.3,
  "indicators": { "rsi": 42.1, "macd_hist": 0.82 },
  "summary": "BUY near Rs1680. Stop loss: Rs1623. Target: Rs1798."
}
```
## Author
Khushi Samundre  
