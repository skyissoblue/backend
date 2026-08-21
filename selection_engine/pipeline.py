"""Incremental market-data download and indicator precomputation pipeline."""
from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from typing import Any

import pandas as pd

from . import data_provider, indicators, local_store
from .config import DETAIL_BATCH_SIZE, REQUEST_DELAY, STATE_FILE, UPDATE_BATCH_SIZE, ensure_dirs
from .database import init_schema, load_stocks, save_update_log, upsert_stocks

logger = logging.getLogger(__name__)


def _board(code: str) -> str:
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith(("688", "689")):
        return "科创板"
    if code.startswith(("4", "8", "92")):
        return "北交所"
    return "主板"


class MarketDataPipeline:
    """Download bounded batches and write all queryable values locally."""

    def __init__(self, batch_size: int = UPDATE_BATCH_SIZE) -> None:
        self.batch_size = max(batch_size, 1)

    def _state(self) -> dict[str, Any]:
        ensure_dirs()
        if not STATE_FILE.exists():
            return {"offset": 0}
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"offset": 0}

    def _save_state(self, state: dict[str, Any]) -> None:
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(STATE_FILE)

    def refresh_universe(self) -> int:
        """Refresh stock names and bulk valuation data."""
        universe = data_provider.get_all_stocks()
        try:
            snapshot = data_provider.get_market_snapshot().set_index("code").to_dict("index")
        except Exception as error:
            logger.warning("bulk quote snapshot failed: %s", error)
            snapshot = {}
        rows = []
        for item in universe.to_dict("records"):
            quote = snapshot.get(item["code"], {})
            rows.append({"code": item["code"], "name": item["name"], "board": _board(item["code"]), **quote})
        upsert_stocks(rows)
        return len(rows)

    def _batch_codes(self) -> tuple[list[str], int]:
        stocks = load_stocks()
        codes = [row["code"] for row in stocks]
        if not codes:
            return [], 0
        state = self._state()
        offset = state.get("offset", 0) % len(codes)
        retry_limit = min(len(state.get("failed_codes", [])), max(1, self.batch_size // 5))
        retries = [code for code in state.get("failed_codes", []) if code in codes][:retry_limit]
        fresh_count = min(self.batch_size - len(retries), len(codes))
        fresh = (codes + codes)[offset:offset + fresh_count]
        selected = list(dict.fromkeys(retries + fresh))
        return selected, (offset + fresh_count) % len(codes)

    def update_batch(self) -> dict[str, Any]:
        """Incrementally update a bounded stock batch and its indicators."""
        codes, next_offset = self._batch_codes()
        metadata = {row["code"]: row for row in load_stocks()}
        updated: list[dict[str, Any]] = []
        failed: list[str] = []
        for index, code in enumerate(codes):
            try:
                existing = local_store.load(code)
                start = None if existing.empty else existing["date"].max().date() - timedelta(days=7)
                fresh = data_provider.get_daily_kline(code, start_date=start)
                if not fresh.empty:
                    local_store.save(code, fresh)
                frame = local_store.load(code)
                if frame.empty:
                    raise ValueError("no local kline data")
                detail = {"code": code, "name": metadata[code]["name"], "board": _board(code)}
                if index < DETAIL_BATCH_SIZE:
                    try:
                        detail.update(data_provider.get_stock_info(code))
                    except Exception as error:
                        logger.warning("stock detail update failed code=%s error=%s", code, error)
                close = float(frame["close"].iloc[-1])
                row = {
                    **detail,
                    "code": code,
                    "close": close,
                    "weekly_ma10": indicators.calc_weekly_ma10(frame),
                    "weekly_deviation": indicators.calc_ma_deviation_weekly(frame),
                    "volume_ratio": indicators.calc_volume_ratio(frame),
                    "listed_days": len(frame),
                }
                updated.append(row)
            except Exception as error:
                failed.append(code)
                logger.warning("stock update failed code=%s error=%s", code, error)
            time.sleep(REQUEST_DELAY)
        upsert_stocks(updated)
        self.precompute_rps()
        factor_stats = None
        if updated:
            try:
                from factor_system.precompute import run_all as run_factors
                factor_stats = run_factors(codes=[row["code"] for row in updated])
            except Exception as error:
                logger.warning("factor precompute failed error=%s", error)
        self._save_state({"offset": next_offset, "failed_codes": failed})
        result = {"selected": len(codes), "updated": len(updated), "failed": len(failed), "failed_codes": failed, "next_offset": next_offset, "factors": factor_stats}
        save_update_log("success" if not failed else "partial", result)
        return result

    def precompute_rps(self) -> int:
        """Rank 250-session returns across every locally available stock."""
        metadata = {row["code"]: row for row in load_stocks()}
        returns: dict[str, float] = {}
        for code in metadata:
            try:
                closes = pd.to_numeric(local_store.load(code)["close"], errors="coerce").dropna().tail(250)
                if len(closes) >= 250 and closes.iloc[0] != 0:
                    returns[code] = float(closes.iloc[-1] / closes.iloc[0] - 1)
            except Exception:
                continue
        if not returns:
            return 0
        ordered = sorted(returns, key=returns.get)
        total = len(ordered)
        rows = [{"code": code, "name": metadata[code]["name"], "rps_250": (index + 1) / total * 100} for index, code in enumerate(ordered)]
        upsert_stocks(rows)
        return total

    def run(self) -> dict[str, Any]:
        """Initialize schema, refresh metadata, then update one data batch."""
        init_schema()
        universe = self.refresh_universe()
        return {"universe": universe, **self.update_batch()}


def main() -> None:
    """Run one scheduled update from the command line."""
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(MarketDataPipeline().run(), ensure_ascii=False))


if __name__ == "__main__":
    main()
