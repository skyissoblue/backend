"""Console and daily rotating file logging."""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler

from .config import LOG_FILE

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        root = logging.getLogger("factor_system")
        root.setLevel(logging.INFO)
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=14, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(console)
        root.addHandler(file_handler)
        _configured = True
    return logging.getLogger(f"factor_system.{name}")
