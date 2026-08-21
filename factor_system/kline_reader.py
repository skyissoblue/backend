"""Bounded, defensive reads from the local Parquet store."""
from __future__ import annotations

import pandas as pd

from .config import KLINE_DIR
from .logger import get_logger

logger = get_logger(__name__)
REQUIRED = {"date", "open", "high", "low", "close", "volume"}


def load(code: str) -> pd.DataFrame | None:
    try:
        path = KLINE_DIR / f"{str(code).zfill(6)}.parquet"
        if not path.is_file():
            return None
        frame = pd.read_parquet(path)
        if frame.empty or not REQUIRED.issubset(frame.columns):
            return None
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date"]).drop_duplicates("date", keep="last").sort_values("date")
        return frame.reset_index(drop=True) if not frame.empty else None
    except Exception as error:
        logger.warning("kline read failed code=%s error=%s", code, error)
        return None


def load_batch(codes: list[str]) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for code in codes:
        frame = load(code)
        if frame is not None:
            result[code] = frame
    return result


def get_all_codes() -> list[str]:
    if not KLINE_DIR.exists():
        return []
    return sorted(path.stem for path in KLINE_DIR.glob("*.parquet") if path.is_file())


def get_last_date(code: str) -> str | None:
    frame = load(code)
    return None if frame is None else frame["date"].iloc[-1].date().isoformat()
