"""Parallel, resumable factor precomputation."""
from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from tqdm import tqdm

from . import kline_reader, redis_store
from .config import BATCH_SIZE, FAILED_FILE, MAX_WORKERS
from .factor_lib.registry import FACTOR_REGISTRY, auto_discover
from .logger import get_logger

logger = get_logger(__name__)


def _factors(kind: str | None) -> list[dict[str, Any]]:
    auto_discover()
    return [item for item in FACTOR_REGISTRY.values() if kind is None or item["kind"] == kind]


def _calculate(code: str, factors: list[dict[str, Any]]) -> tuple[str, dict[str, Any], int]:
    frame = kline_reader.load(code)
    if frame is None:
        return code, {}, len(factors)
    result: dict[str, Any] = {"factor_date": frame["date"].iloc[-1].date().isoformat()}
    failures = 0
    for item in factors:
        try:
            value = item["func"](frame)
            values = value if isinstance(value, dict) else {item["fields"][0]: value}
            for field, field_value in values.items():
                if field_value is not None and not (isinstance(field_value, float) and not math.isfinite(field_value)):
                    result[field] = int(field_value) if isinstance(field_value, bool) else field_value
        except Exception as error:
            failures += 1
            logger.debug("factor failed code=%s factor=%s error=%s", code, item["name"], error)
    return code, result, failures


def run_single(code: str, kind: str | None = None) -> dict[str, Any]:
    _, values, _ = _calculate(str(code).zfill(6), _factors(kind))
    return values


def run_all(kind: str | None = None, codes: list[str] | None = None) -> dict[str, Any]:
    factors = _factors(kind)
    selected = [str(code).zfill(6) for code in codes] if codes else kline_reader.get_all_codes()
    succeeded, failed, partial, pending = 0, [], 0, {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_calculate, code, factors): code for code in selected}
        for future in tqdm(as_completed(futures), total=len(futures), desc=f"factors:{kind or 'all'}"):
            code = futures[future]
            try:
                _, values, failures = future.result()
                if not values or failures == len(factors):
                    failed.append(code)
                    continue
                partial += int(failures > 0)
                pending[code] = values
                succeeded += 1
                if len(pending) >= BATCH_SIZE:
                    redis_store.batch_set_hash("stock", pending)
                    pending.clear()
            except Exception:
                failed.append(code)
                logger.exception("stock factor calculation failed code=%s", code)
    if pending:
        redis_store.batch_set_hash("stock", pending)
    FAILED_FILE.parent.mkdir(parents=True, exist_ok=True)
    FAILED_FILE.write_text(json.dumps({"kind": kind, "codes": failed}, ensure_ascii=False), encoding="utf-8")
    stats = {"total": len(selected), "success": succeeded, "failed": len(failed), "partial": partial, "factor_count": len(factors)}
    logger.info("factor run complete: %s", stats)
    return stats


def resume_failed(log_file=FAILED_FILE) -> dict[str, Any]:
    state = json.loads(log_file.read_text(encoding="utf-8"))
    return run_all(state.get("kind"), state.get("codes") or [])
