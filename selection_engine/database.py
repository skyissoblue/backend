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


def create_user(phone: str, nickname: str | None, password_hash: str) -> dict[str, Any]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users(phone,nickname,password_hash) VALUES (%s,%s,%s)", (phone, nickname, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
    return {"id": user_id, "phone": phone, "nickname": nickname}


def _one(sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
    return row


def get_user_by_phone(phone: str) -> dict[str, Any] | None:
    return _one("SELECT id,phone,nickname,password_hash FROM users WHERE phone=%s", (phone,))


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    return _one("SELECT id,phone,nickname FROM users WHERE id=%s", (user_id,))


def create_combo(user_id: int, name: str, total: int) -> int:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO selection_combos(user_id,name,conditions_json,result_codes,result_count) VALUES (%s,%s,%s,%s,%s)", (user_id, name, "[]", "[]", total))
        conn.commit(); combo_id = cursor.lastrowid; cursor.close()
    return combo_id


def list_combos(user_id: int, favorite: bool | None = None) -> list[dict[str, Any]]:
    sql = "SELECT id,name,conditions_json,result_codes,result_count,is_favorite FROM selection_combos WHERE user_id=%s"
    params: tuple[Any, ...] = (user_id,)
    if favorite is not None:
        sql += " AND is_favorite=%s"; params += (int(favorite),)
    sql += " ORDER BY updated_at DESC"
    with connection() as conn:
        cursor = conn.cursor(dictionary=True); cursor.execute(sql, params); rows = cursor.fetchall(); cursor.close()
    return rows


def get_combo(user_id: int, combo_id: int) -> dict[str, Any] | None:
    return _one("SELECT id,name,conditions_json,result_codes,result_count,is_favorite FROM selection_combos WHERE id=%s AND user_id=%s", (combo_id, user_id))


def update_combo(user_id: int, combo_id: int, **values: Any) -> None:
    allowed = {"name", "conditions_json", "result_codes", "result_count", "is_favorite"}
    values = {key: value for key, value in values.items() if key in allowed}
    if not values: return
    sql = "UPDATE selection_combos SET " + ",".join(f"{key}=%s" for key in values) + " WHERE id=%s AND user_id=%s"
    with connection() as conn:
        cursor = conn.cursor(); cursor.execute(sql, (*values.values(), combo_id, user_id)); conn.commit(); cursor.close()


def delete_combo(user_id: int, combo_id: int) -> None:
    with connection() as conn:
        cursor = conn.cursor(); cursor.execute("DELETE FROM selection_combos WHERE id=%s AND user_id=%s", (combo_id, user_id)); conn.commit(); cursor.close()


def upsert_watchlist(user_id: int, code: str, name: str | None, combo_id: int | None, combo_name: str | None) -> None:
    with connection() as conn:
        cursor = conn.cursor(); cursor.execute("INSERT INTO watchlist(user_id,stock_code,stock_name,source_combo_id,source_combo_name) VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE stock_name=VALUES(stock_name),source_combo_id=VALUES(source_combo_id),source_combo_name=VALUES(source_combo_name)", (user_id, code, name, combo_id, combo_name)); conn.commit(); cursor.close()


def list_watchlist(user_id: int) -> list[dict[str, Any]]:
    with connection() as conn:
        cursor = conn.cursor(dictionary=True); cursor.execute("SELECT stock_code,stock_name,source_combo_id,source_combo_name,note,created_at FROM watchlist WHERE user_id=%s ORDER BY source_combo_name,created_at DESC", (user_id,)); rows = cursor.fetchall(); cursor.close()
    return rows


def delete_watchlist(user_id: int, code: str) -> None:
    with connection() as conn:
        cursor = conn.cursor(); cursor.execute("DELETE FROM watchlist WHERE user_id=%s AND stock_code=%s", (user_id, code)); conn.commit(); cursor.close()
