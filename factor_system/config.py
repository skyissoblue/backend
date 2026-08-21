"""Factor-system configuration."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("STOCK_DATA_DIR", os.getenv("DATA_DIR", "./data")))
KLINE_DIR = DATA_DIR / "kline"
FAILED_FILE = DATA_DIR / "factor_failed.json"
LOG_FILE = DATA_DIR / "factor.log"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BATCH_SIZE = int(os.getenv("FACTOR_BATCH_SIZE", "500"))
MAX_WORKERS = int(os.getenv("FACTOR_MAX_WORKERS", "4"))
RETRY_TIMES = int(os.getenv("FACTOR_RETRY_TIMES", "3"))
