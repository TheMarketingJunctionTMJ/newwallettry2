import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent / 'trades.db'


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('LONG', 'SHORT')),
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'CLOSED')),
                close_price REAL,
                realized_pnl REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            )
            '''
        )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def add_trade(symbol: str, side: str, quantity: float, entry_price: float) -> None:
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO trades (symbol, side, quantity, entry_price)
            VALUES (?, ?, ?, ?)
            ''',
            (symbol.upper(), side.upper(), quantity, entry_price),
        )
        conn.commit()



def get_all_trades() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            '''
            SELECT *
            FROM trades
            ORDER BY
                CASE WHEN status = 'OPEN' THEN 0 ELSE 1 END,
                datetime(created_at) DESC,
                id DESC
            '''
        ).fetchall()
    return [dict(row) for row in rows]



def get_trade(trade_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM trades WHERE id = ?', (trade_id,)).fetchone()
    return dict(row) if row else None



def close_trade(trade_id: int, close_price: float) -> None:
    trade = get_trade(trade_id)
    if not trade:
        raise ValueError('Trade not found.')
    if trade['status'] == 'CLOSED':
        raise ValueError('Trade is already closed.')

    quantity = float(trade['quantity'])
    entry_price = float(trade['entry_price'])
    side = trade['side']

    realized_pnl = (close_price - entry_price) * quantity if side == 'LONG' else (entry_price - close_price) * quantity

    with get_conn() as conn:
        conn.execute(
            '''
            UPDATE trades
            SET status = 'CLOSED',
                close_price = ?,
                realized_pnl = ?,
                closed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (close_price, realized_pnl, trade_id),
        )
        conn.commit()
