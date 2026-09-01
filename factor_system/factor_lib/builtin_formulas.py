"""Composite factors backing named built-in selection formulas."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .registry import register

try:
    import talib
except ImportError:
    talib = None


def _period_close(frame: pd.DataFrame, rule: str) -> np.ndarray:
    data = frame.loc[:, ["date", "close"]].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    values = (
        data.dropna()
        .drop_duplicates("date", keep="last")
        .set_index("date")["close"]
        .sort_index()
        .resample(rule)
        .last()
        .dropna()
    )
    return values.to_numpy(dtype="float64")


def _rsi_pair(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if talib is None:
        return np.array([]), np.array([])
    return talib.RSI(close, timeperiod=6), talib.RSI(close, timeperiod=12)


def _monthly_setup(fast: np.ndarray, slow: np.ndarray) -> bool:
    if len(fast) < 3 or len(slow) != len(fast):
        return False
    valid = np.isfinite(fast) & np.isfinite(slow)
    crosses = np.flatnonzero(
        valid[1:] & valid[:-1] & (fast[:-1] <= slow[:-1]) & (fast[1:] > slow[1:])
    ) + 1
    if not len(crosses):
        return False
    last_cross = int(crosses[-1])
    if last_cross >= len(fast) - 1:
        return False
    reached_70 = bool(np.nanmax(fast[last_cross:]) >= 70)
    pulling_back = bool(fast[-1] < fast[-2])
    holding_slow = bool(fast[-1] >= slow[-1])
    gap_narrowing = bool((fast[-1] - slow[-1]) <= (fast[-2] - slow[-2]))
    return reached_70 and pulling_back and holding_slow and gap_narrowing


def _weekly_golden_cross(fast: np.ndarray, slow: np.ndarray) -> bool:
    return bool(
        len(fast) >= 2
        and len(slow) == len(fast)
        and np.isfinite(fast[-2:]).all()
        and np.isfinite(slow[-2:]).all()
        and fast[-2] <= slow[-2]
        and fast[-1] > slow[-1]
    )


def mmc_rsi(frame: pd.DataFrame) -> bool | None:
    """Monthly RSI pullback setup confirmed by a current weekly RSI golden cross."""
    if talib is None or len(frame) < 260:
        return None
    monthly_fast, monthly_slow = _rsi_pair(_period_close(frame, "ME"))
    weekly_fast, weekly_slow = _rsi_pair(_period_close(frame, "W-FRI"))
    return _monthly_setup(monthly_fast, monthly_slow) and _weekly_golden_cross(
        weekly_fast, weekly_slow
    )


register(
    "mmc_rsi",
    "pattern",
    mmc_rsi,
    desc="月线RSI6金叉后达到70并回踩不破RSI12，同时周线RSI6金叉RSI12",
)

