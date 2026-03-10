"""
Tests for the SQLite portfolio manager in database/portfolio_db.py

Run with: pytest tests/test_portfolio.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# use a test-only database so we don't mess up real data
import database.portfolio_db as db

TEST_PID = "test_portfolio_unit"


def setup_function():
    """Reset test portfolio before each test."""
    with db._connect() as conn:
        conn.execute("DELETE FROM positions  WHERE portfolio_id = ?", (TEST_PID,))
        conn.execute("DELETE FROM trade_log  WHERE portfolio_id = ?", (TEST_PID,))
        conn.execute("DELETE FROM portfolios WHERE id = ?", (TEST_PID,))
        conn.execute(
            "INSERT INTO portfolios (id, cash_balance) VALUES (?, ?)",
            (TEST_PID, 500_000)
        )


# ── buy tests ─────────────────────────────────────────────────────────

def test_buy_creates_position():
    db.execute_buy(TEST_PID, "RELIANCE.NS", 10, 2500.0)
    pos = db.get_position(TEST_PID, "RELIANCE.NS")
    assert pos is not None
    assert pos["quantity"] == 10
    assert pos["avg_price"] == 2500.0

def test_buy_deducts_cash():
    db.execute_buy(TEST_PID, "TCS.NS", 5, 3000.0)
    portfolio = db.get_portfolio(TEST_PID)
    assert portfolio["cash_balance"] == 500_000 - (5 * 3000)

def test_buy_averages_price():
    db.execute_buy(TEST_PID, "INFY.NS", 10, 1000.0)
    db.execute_buy(TEST_PID, "INFY.NS", 10, 2000.0)
    pos = db.get_position(TEST_PID, "INFY.NS")
    # avg should be (10*1000 + 10*2000) / 20 = 1500
    assert pos["avg_price"] == 1500.0
    assert pos["quantity"] == 20

def test_buy_fails_if_insufficient_funds():
    result = db.execute_buy(TEST_PID, "BAJFINANCE.NS", 1000, 7000.0)
    assert "error" in result


# ── sell tests ────────────────────────────────────────────────────────

def test_sell_reduces_position():
    db.execute_buy(TEST_PID, "HDFCBANK.NS", 20, 1500.0)
    db.execute_sell(TEST_PID, "HDFCBANK.NS", 5, 1600.0)
    pos = db.get_position(TEST_PID, "HDFCBANK.NS")
    assert pos["quantity"] == 15

def test_sell_all_removes_position():
    db.execute_buy(TEST_PID, "WIPRO.NS", 10, 400.0)
    db.execute_sell(TEST_PID, "WIPRO.NS", 10, 420.0)
    pos = db.get_position(TEST_PID, "WIPRO.NS")
    assert pos is None

def test_sell_calculates_pnl():
    db.execute_buy(TEST_PID, "NTPC.NS", 100, 200.0)
    result = db.execute_sell(TEST_PID, "NTPC.NS", 100, 220.0)
    # pnl = (220 - 200) * 100 = 2000
    assert result["realized_pnl"] == 2000.0

def test_sell_more_than_held_fails():
    db.execute_buy(TEST_PID, "SBIN.NS", 10, 600.0)
    result = db.execute_sell(TEST_PID, "SBIN.NS", 50, 620.0)
    assert "error" in result

def test_sell_nothing_held_fails():
    result = db.execute_sell(TEST_PID, "TATASTEEL.NS", 5, 100.0)
    assert "error" in result