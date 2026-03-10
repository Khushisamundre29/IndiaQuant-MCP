"""
IndiaQuant MCP Server
This is the entry point. It registers all 10 tools with the MCP protocol
and routes Claude's tool calls to the right module.
"""

import sys
import json
import asyncio
import logging

# make sure Python can find our modules from the project root
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

# import all 5 tool files
from tools import price_tool, signal_tool, options_tool, portfolio_tool, market_tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("indiaquant")

app = Server("indiaquant-mcp")


# ── 1. Register tools ─────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        types.Tool(
            name="get_live_price",
            description=(
                "Get real-time price, change%, and volume for any NSE or BSE stock. "
                "Use .NS suffix for NSE stocks (e.g. RELIANCE.NS, HDFCBANK.NS). "
                "For indices use ^NSEI (Nifty50) or ^NSEBANK (BankNifty)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "e.g. RELIANCE.NS or ^NSEI"},
                },
                "required": ["symbol"],
            },
        ),

        types.Tool(
            name="get_options_chain",
            description=(
                "Fetch the live options chain (calls + puts) for a stock or index. "
                "Includes strike prices, open interest, volume, IV, and Black-Scholes Greeks. "
                "Also returns max pain and PCR."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "e.g. RELIANCE.NS or ^NSEI"},
                    "expiry": {"type": "string", "description": "YYYY-MM-DD. Leave blank for nearest expiry."},
                },
                "required": ["symbol"],
            },
        ),

        types.Tool(
            name="analyze_sentiment",
            description=(
                "Analyze news sentiment for a stock. "
                "Returns a score from -1 (very negative) to +1 (very positive), "
                "top headlines, and a POSITIVE / NEUTRAL / NEGATIVE signal."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "e.g. RELIANCE or TCS"},
                },
                "required": ["symbol"],
            },
        ),

        types.Tool(
            name="generate_signal",
            description=(
                "Generate a BUY / SELL / HOLD trade signal with confidence score (0-100%). "
                "Uses RSI, MACD, Bollinger Bands, EMA trend, volume, and news sentiment. "
                "Also returns support/resistance levels."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":    {"type": "string",  "description": "e.g. RELIANCE.NS"},
                    "timeframe": {
                        "type": "string",
                        "description": "1d (daily), 1wk (weekly), 1mo (monthly). Default: 1d",
                        "enum": ["1d", "1wk", "1mo"],
                    },
                },
                "required": ["symbol"],
            },
        ),

        types.Tool(
            name="get_portfolio_pnl",
            description=(
                "Show real-time P&L for your virtual portfolio. "
                "Fetches live prices for all positions and calculates "
                "unrealized gain/loss, risk score, and any stop-loss/target alerts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "portfolio_id": {
                        "type": "string",
                        "description": "Portfolio name. Default: 'default'",
                    },
                },
                "required": [],
            },
        ),

        types.Tool(
            name="place_virtual_trade",
            description=(
                "Place a paper trade (virtual buy or sell). "
                "No real money involved. Executes at the current live price. "
                "You can optionally set a stop loss and target."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":       {"type": "string",  "description": "e.g. RELIANCE.NS"},
                    "quantity":     {"type": "integer", "description": "Number of shares"},
                    "side":         {"type": "string",  "description": "BUY or SELL", "enum": ["BUY", "SELL"]},
                    "portfolio_id": {"type": "string",  "description": "Default: 'default'"},
                    "stop_loss":    {"type": "number",  "description": "Stop loss price (optional)"},
                    "target":       {"type": "number",  "description": "Target price (optional)"},
                },
                "required": ["symbol", "quantity", "side"],
            },
        ),

        types.Tool(
            name="calculate_greeks",
            description=(
                "Calculate Black-Scholes option Greeks (Delta, Gamma, Theta, Vega) "
                "for any NSE option contract. Implemented from scratch — no library used."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":      {"type": "string",  "description": "Underlying e.g. RELIANCE.NS"},
                    "strike":      {"type": "number",  "description": "Strike price"},
                    "expiry":      {"type": "string",  "description": "Expiry date YYYY-MM-DD"},
                    "option_type": {"type": "string",  "description": "CE or PE", "enum": ["CE", "PE"]},
                    "iv":          {"type": "number",  "description": "Implied volatility 0-1 (e.g. 0.25). Leave 0 to auto-fetch."},
                },
                "required": ["symbol", "strike", "expiry", "option_type"],
            },
        ),

        types.Tool(
            name="detect_unusual_activity",
            description=(
                "Detect unusually high options volume vs open interest. "
                "Flags contracts where volume is 2x (or more) the OI, "
                "which often signals a large directional bet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol":    {"type": "string", "description": "e.g. RELIANCE.NS or ^NSEI"},
                    "threshold": {"type": "number", "description": "Vol/OI ratio to flag. Default: 2.0"},
                },
                "required": ["symbol"],
            },
        ),

        types.Tool(
            name="scan_market",
            description=(
                "Scan Nifty 50 stocks using a technical filter. "
                "Example: find oversold IT stocks, or momentum plays. "
                "Filters: oversold, overbought, bullish_macd, bearish_macd, "
                "near_52w_high, near_52w_low, volume_surge, momentum."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_type": {
                        "type": "string",
                        "description": "oversold | overbought | bullish_macd | bearish_macd | near_52w_high | near_52w_low | volume_surge | momentum",
                    },
                    "sector": {
                        "type": "string",
                        "description": "IT | Banking | Auto | Pharma | FMCG | Energy | Metal | Finance | all. Default: all",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "How many results to return. Default: 10",
                    },
                },
                "required": ["filter_type"],
            },
        ),

        types.Tool(
            name="get_sector_heatmap",
            description=(
                "Get the current % change for all major NSE sector indices. "
                "Shows which sectors are up/down today."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


# ── 2. Handle tool calls ──────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    log.info(f"Tool called: {name} | args: {arguments}")

    try:
        if name == "get_live_price":
            result = price_tool.run(arguments["symbol"])

        elif name == "get_options_chain":
            result = options_tool.run_options_chain(
                arguments["symbol"],
                arguments.get("expiry", ""),
            )

        elif name == "analyze_sentiment":
            result = __import__("modules.sentiment", fromlist=["fetch_sentiment"]).fetch_sentiment(
                arguments["symbol"]
            )

        elif name == "generate_signal":
            result = signal_tool.run(
                arguments["symbol"],
                arguments.get("timeframe", "1d"),
            )

        elif name == "get_portfolio_pnl":
            result = portfolio_tool.run_pnl(
                arguments.get("portfolio_id", "default")
            )

        elif name == "place_virtual_trade":
            result = portfolio_tool.run_trade(
                symbol       = arguments["symbol"],
                quantity     = arguments["quantity"],
                side         = arguments["side"],
                portfolio_id = arguments.get("portfolio_id", "default"),
                stop_loss    = arguments.get("stop_loss"),
                target       = arguments.get("target"),
            )

        elif name == "calculate_greeks":
            result = options_tool.run_greeks(
                symbol      = arguments["symbol"],
                strike      = arguments["strike"],
                expiry      = arguments["expiry"],
                option_type = arguments["option_type"],
                iv          = arguments.get("iv", 0.0),
            )

        elif name == "detect_unusual_activity":
            result = options_tool.run_unusual_activity(
                arguments["symbol"],
                arguments.get("threshold", 2.0),
            )

        elif name == "scan_market":
            result = market_tool.run_scan(
                filter_type = arguments["filter_type"],
                sector      = arguments.get("sector", "all"),
                top_n       = arguments.get("top_n", 10),
            )

        elif name == "get_sector_heatmap":
            result = market_tool.run_heatmap()

        else:
            result = {"error": f"Unknown tool: {name}"}

    except Exception as e:
        log.error(f"Error in {name}: {e}", exc_info=True)
        result = {"error": str(e), "tool": name}

    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ── 3. Start server ───────────────────────────────────────────────────

async def main():
    log.info("IndiaQuant MCP server starting...")
    async with mcp.server.stdio.stdio_server() as (read, write):
        await app.run(
            read,
            write,
            InitializationOptions(
                server_name    = "indiaquant-mcp",
                server_version = "1.0.0",
                capabilities   = types.ServerCapabilities(
                    tools=types.ToolsCapability(),
                    experimental={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())