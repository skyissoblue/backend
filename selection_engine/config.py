"""Environment-driven configuration for local market-data storage."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("STOCK_DATA_DIR", "/data"))
KLINE_DIR = DATA_DIR / "kline"
STATE_FILE = DATA_DIR / "pipeline_state.json"
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "mysql"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "stock_picker"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DB", "stock_picker"),
    "charset": "utf8mb4",
}
UPDATE_BATCH_SIZE = int(os.getenv("UPDATE_BATCH_SIZE", "200"))
DETAIL_BATCH_SIZE = int(os.getenv("DETAIL_BATCH_SIZE", "5"))
UPDATE_INTERVAL_MINUTES = int(os.getenv("UPDATE_INTERVAL_MINUTES", "60"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.3"))
SCHEDULER_ENABLED = os.getenv("DATA_SCHEDULER_ENABLED", "false").lower() == "true"


def ensure_dirs() -> None:
    """Create persistent data directories."""
    KLINE_DIR.mkdir(parents=True, exist_ok=True)
