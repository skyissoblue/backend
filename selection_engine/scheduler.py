"""Background scheduler for incremental local market-data updates."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .config import SCHEDULER_ENABLED, UPDATE_INTERVAL_MINUTES
from .pipeline import MarketDataPipeline

logger = logging.getLogger(__name__)
_scheduler: Any | None = None


def _update() -> None:
    try:
        result = MarketDataPipeline().run()
        logger.info("market data update complete: %s", result)
    except Exception:
        logger.exception("market data update failed")


def start_scheduler() -> None:
    """Start the single-process interval scheduler when enabled."""
    global _scheduler
    if not SCHEDULER_ENABLED or _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(
        _update,
        "interval",
        minutes=UPDATE_INTERVAL_MINUTES,
        id="market-data-update",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(seconds=15),
    )
    _scheduler.start()
    logger.info("market data scheduler started interval=%s minutes", UPDATE_INTERVAL_MINUTES)


def stop_scheduler() -> None:
    """Stop the scheduler cleanly."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
