"""Resumable full-history backfill for every locally registered A-share."""
from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

from . import data_provider, indicators, local_store
from .config import DATA_DIR, REQUEST_DELAY
from .database import init_schema, load_stocks, upsert_stocks

logger = logging.getLogger(__name__)

HISTORY_START = date.fromisoformat(os.getenv("A_SHARE_HISTORY_START", "1990-01-01"))
HISTORY_WORKERS = max(1, int(os.getenv("A_SHARE_HISTORY_WORKERS", "4")))
STATE_FILE = Path(os.getenv("A_SHARE_HISTORY_STATE_FILE", str(DATA_DIR / "a_share_history_state.json")))


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"completed": [], "failed": {}}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {
            "completed": list(state.get("completed", [])),
            "failed": dict(state.get("failed", {})),
        }
    except Exception:
        return {"completed": [], "failed": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary.replace(STATE_FILE)


def _download(code: str, name: str) -> tuple[str, int, dict[str, Any]]:
    frame = data_provider.get_daily_kline(code, start_date=HISTORY_START)
    if frame.empty:
        raise ValueError("empty full-history response")
    local_store.save(code, frame)
    stored = local_store.load(code)
    row: dict[str, Any] = {
        "code": code,
        "name": name,
        "close": float(stored["close"].iloc[-1]),
        "listed_days": len(stored),
    }
    if len(stored) >= 50:
        row.update(
            weekly_ma10=indicators.calc_weekly_ma10(stored),
            weekly_deviation=indicators.calc_ma_deviation_weekly(stored),
            volume_ratio=indicators.calc_volume_ratio(stored),
        )
    for window in (5, 10, 20, 60, 120, 250):
        if len(stored) >= window:
            row[f"daily_ma{window}"] = indicators.calc_period_ma(stored, window, "daily")
    time.sleep(REQUEST_DELAY)
    return code, len(stored), row


def run(limit: int | None = None) -> dict[str, Any]:
    """Download all available A-share bars, resuming at stock granularity."""
    init_schema()
    stocks = [row for row in load_stocks() if row.get("board") != "ETF"]
    state = _load_state()
    completed = set(state["completed"])
    pending = [row for row in stocks if row["code"] not in completed]
    if limit is not None:
        pending = pending[: max(limit, 0)]
    succeeded = 0
    failed = 0
    rows = 0
    with ThreadPoolExecutor(max_workers=HISTORY_WORKERS) as executor:
        futures = {
            executor.submit(_download, row["code"], row["name"]): row["code"]
            for row in pending
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                _, count, snapshot = future.result()
                upsert_stocks([snapshot])
                completed.add(code)
                state["completed"] = sorted(completed)
                state["failed"].pop(code, None)
                succeeded += 1
                rows += count
                logger.info("history saved code=%s rows=%s progress=%s/%s", code, count, succeeded + failed, len(pending))
            except Exception as error:
                failed += 1
                state["failed"][code] = str(error)
                logger.warning("history failed code=%s error=%s", code, error)
            _save_state(state)
    return {
        "total_stocks": len(stocks),
        "pending": len(pending),
        "succeeded": succeeded,
        "failed": failed,
        "completed_total": len(completed),
        "rows_saved": rows,
        "state_file": str(STATE_FILE),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    limit_value = os.getenv("A_SHARE_HISTORY_LIMIT")
    result = run(int(limit_value) if limit_value else None)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
