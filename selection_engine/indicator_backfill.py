"""Backfill precomputed indicators from locally stored K-line files."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import indicators, local_store
from .database import init_schema, load_stocks, upsert_stocks

WORKERS = max(1, int(os.getenv("INDICATOR_BACKFILL_WORKERS", "8")))
BATCH_SIZE = max(1, int(os.getenv("INDICATOR_BACKFILL_BATCH_SIZE", "500")))


def _daily_mas(stock: dict[str, Any]) -> dict[str, Any] | None:
    frame = local_store.load(stock["code"])
    if len(frame) < 5:
        return None
    row = {
        "code": stock["code"],
        "name": stock["name"],
    }
    for window in (5, 10, 20, 60, 120, 250):
        if len(frame) >= window:
            row[f"daily_ma{window}"] = indicators.calc_period_ma(frame, window, "daily")
    return row


def run() -> dict[str, int]:
    """Compute MA250 once so interactive selection never scans every file."""
    init_schema()
    stocks = load_stocks()
    updated = 0
    batch: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        for row in executor.map(_daily_mas, stocks):
            if row is None:
                continue
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                upsert_stocks(batch)
                updated += len(batch)
                batch.clear()
    if batch:
        upsert_stocks(batch)
        updated += len(batch)
    return {"total": len(stocks), "updated": updated}


if __name__ == "__main__":
    print(run())
