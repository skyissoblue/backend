"""Atomic Parquet persistence for daily stock bars."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .config import KLINE_DIR, ensure_dirs


def path_for(code: str) -> Path:
    """Return the normalized Parquet path for a stock."""
    return KLINE_DIR / f"{str(code).zfill(6)}.parquet"


def load(code: str) -> pd.DataFrame:
    """Load locally stored bars, returning an empty frame if absent."""
    path = path_for(code)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame.dropna(subset=["date"]).drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def save(code: str, frame: pd.DataFrame) -> None:
    """Atomically merge and save normalized daily bars."""
    ensure_dirs()
    required = {"date", "open", "high", "low", "close", "volume", "amount"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError(f"invalid kline frame for {code}")
    existing = load(code)
    merged = pd.concat([existing, frame], ignore_index=True) if not existing.empty else frame.copy()
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.dropna(subset=["date"]).drop_duplicates("date", keep="last").sort_values("date")
    target = path_for(code)
    temporary = target.with_suffix(f".parquet.tmp.{os.getpid()}")
    merged.to_parquet(temporary, index=False, engine="pyarrow", compression="snappy")
    os.replace(temporary, target)
