import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")

def _connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id TEXT PRIMARY KEY,
            cash_balance REAL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id TEXT,
            symbol TEXT,
            quantity REAL,
            avg_price REAL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id TEXT,
            symbol TEXT,
            side TEXT,
            quantity REAL,
            price REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

def get_portfolio(portfolio_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)
        ).fetchone()
        if row:
            return {"id": row[0], "cash_balance": row[1]}
        return None

def get_positions(portfolio_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT symbol, quantity, avg_price FROM positions WHERE portfolio_id = ?",
            (portfolio_id,)
        ).fetchall()
        return [
            {"symbol": r[0], "quantity": r[1], "avg_price": r[2]}
            for r in rows
        ]

def get_position(portfolio_id: str, symbol: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT symbol, quantity, avg_price FROM positions WHERE portfolio_id = ? AND symbol = ?",
            (portfolio_id, symbol)
        ).fetchone()
        if row:
            return {"symbol": row[0], "quantity": row[1], "avg_price": row[2]}
        return None

def execute_buy(portfolio_id: str, symbol: str, quantity: float, price: float, stop_loss=None, target=None) -> dict:
    with _connect() as conn:
        portfolio = get_portfolio(portfolio_id)
        if not portfolio:
            return {"error": f"Portfolio '{portfolio_id}' not found"}

        cost = quantity * price
        if portfolio["cash_balance"] < cost:
            return {"error": "Insufficient funds"}

        conn.execute(
            "UPDATE portfolios SET cash_balance = cash_balance - ? WHERE id = ?",
            (cost, portfolio_id)
        )

        existing = get_position(portfolio_id, symbol)
        if existing:
            new_qty = existing["quantity"] + quantity
            new_avg = ((existing["quantity"] * existing["avg_price"]) + (quantity * price)) / new_qty
            conn.execute(
                "UPDATE positions SET quantity = ?, avg_price = ? WHERE portfolio_id = ? AND symbol = ?",
                (new_qty, new_avg, portfolio_id, symbol)
            )
        else:
            conn.execute(
                "INSERT INTO positions (portfolio_id, symbol, quantity, avg_price) VALUES (?, ?, ?, ?)",
                (portfolio_id, symbol, quantity, price)
            )

        conn.execute(
            "INSERT INTO trade_log (portfolio_id, symbol, side, quantity, price) VALUES (?, ?, 'BUY', ?, ?)",
            (portfolio_id, symbol, quantity, price)
        )

        conn.commit()
        return {"success": True}

def execute_sell(portfolio_id: str, symbol: str, quantity: float, price: float) -> dict:
    with _connect() as conn:
        position = get_position(portfolio_id, symbol)
        if not position or position["quantity"] < quantity:
            return {"error": "Insufficient position"}

        realized_pnl = (price - position["avg_price"]) * quantity

        proceeds = quantity * price
        conn.execute(
            "UPDATE portfolios SET cash_balance = cash_balance + ? WHERE id = ?",
            (proceeds, portfolio_id)
        )

        new_qty = position["quantity"] - quantity
        if new_qty == 0:
            conn.execute(
                "DELETE FROM positions WHERE portfolio_id = ? AND symbol = ?",
                (portfolio_id, symbol)
            )
        else:
            conn.execute(
                "UPDATE positions SET quantity = ? WHERE portfolio_id = ? AND symbol = ?",
                (new_qty, portfolio_id, symbol)
            )

        conn.execute(
            "INSERT INTO trade_log (portfolio_id, symbol, side, quantity, price) VALUES (?, ?, 'SELL', ?, ?)",
            (portfolio_id, symbol, quantity, price)
        )

        conn.commit()
        return {"success": True, "realized_pnl": realized_pnl}