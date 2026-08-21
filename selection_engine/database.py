"""MySQL connection pool and stock snapshot repository."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from .config import MYSQL_CONFIG

_pool: Any | None = None
_lock = Lock()


def pool() -> Any:
    """Return the process-wide MySQL connection pool."""
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                from mysql.connector.pooling import MySQLConnectionPool
                _pool = MySQLConnectionPool(pool_name="stock_picker", pool_size=10, **MYSQL_CONFIG)
    return _pool


@contextmanager
def connection() -> Iterator[Any]:
    """Yield a pooled connection and always return it to the pool."""
    conn = pool().get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_schema() -> None:
    """Create or upgrade the application schema."""
    sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with connection() as conn:
        cursor = conn.cursor()
        for statement in (part.strip() for part in sql.split(";") if part.strip()):
            cursor.execute(statement)
        conn.commit()
        cursor.close()


def health_check() -> bool:
    """Return whether MySQL accepts a ping."""
    try:
        with connection() as conn:
            conn.ping(reconnect=True, attempts=1, delay=0)
        return True
    except Exception:
        return False


def upsert_stocks(stocks: list[dict[str, Any]]) -> int:
    """Batch upsert stock metadata and precomputed indicators."""
    if not stocks:
        return 0
    columns = ("code", "name", "industry", "board", "close", "weekly_ma10", "weekly_deviation", "rps_250", "volume_ratio", "market_cap", "pe", "listed_days")
    placeholders = ",".join(["%s"] * len(columns))
    updates = ",".join(f"{name}=COALESCE(VALUES({name}),{name})" for name in columns[1:])
    sql = f"INSERT INTO stocks ({','.join(columns)}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}"
    values = [tuple(stock.get(column) for column in columns) for stock in stocks]
    with connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(sql, values)
        conn.commit()
        count = cursor.rowcount
        cursor.close()
    return count


def load_stocks(limit: int | None = None) -> list[dict[str, Any]]:
    """Load the complete local stock snapshot without external requests."""
    sql = "SELECT code,name,industry,board,close,weekly_ma10,weekly_deviation,rps_250,volume_ratio,market_cap,pe,listed_days FROM stocks ORDER BY code"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT %s"
        params = (limit,)
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
    return rows


def save_update_log(status: str, details: dict[str, Any]) -> None:
    """Persist one pipeline execution summary."""
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO update_log(status, details_json) VALUES (%s,%s)", (status, json.dumps(details, ensure_ascii=False)))
        conn.commit()
        cursor.close()
