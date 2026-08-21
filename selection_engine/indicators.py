"""Technical indicators used by progressive selection."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import pandas as pd

def _close_series(data: Any) -> pd.Series:
    if isinstance(data, pd.DataFrame): series = data["close"]
    elif isinstance(data, pd.Series): series = data
    else: raise TypeError("close data must be a DataFrame or Series")
    return pd.to_numeric(series, errors="coerce").dropna()

def calc_weekly_ma10(df: pd.DataFrame) -> float:
    if df.empty or not {"date", "close"}.issubset(df.columns): raise ValueError("daily kline requires date and close columns")
    frame = df.loc[:, ["date", "close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    weekly = frame.dropna().set_index("date")["close"].sort_index().resample("W-FRI").last().dropna()
    if len(weekly) < 10: raise ValueError("at least 10 weeks of data are required")
    return float(weekly.rolling(10).mean().iloc[-1])

def calc_rps_250(code: str, all_closes: Mapping[str, Any]) -> float:
    returns: dict[str, float] = {}
    for stock_code, values in all_closes.items():
        if isinstance(values, (int, float)): returns[stock_code] = float(values); continue
        closes = _close_series(values).tail(250)
        if len(closes) >= 2 and closes.iloc[0] != 0: returns[stock_code] = float(closes.iloc[-1] / closes.iloc[0] - 1)
    if code not in returns: raise ValueError(f"no 250-day close data for {code}")
    return float(sum(value <= returns[code] for value in returns.values()) / len(returns) * 100)

def calc_volume_ratio(df: pd.DataFrame) -> float:
    if "volume" not in df.columns: raise ValueError("daily kline requires volume column")
    volume = pd.to_numeric(df["volume"], errors="coerce").dropna()
    if len(volume) < 5: raise ValueError("at least 5 trading days are required")
    average = float(volume.tail(5).mean())
    if average == 0: raise ValueError("5-day average volume is zero")
    return float(volume.iloc[-1] / average)

def calc_ma_deviation_weekly(df: pd.DataFrame) -> float:
    close = _close_series(df)
    if close.empty: raise ValueError("daily kline has no valid close")
    ma10 = calc_weekly_ma10(df)
    return float((close.iloc[-1] - ma10) / ma10 * 100)


def calc_macd_cross(df: pd.DataFrame) -> bool:
    close = _close_series(df)
    if len(close) < 35: raise ValueError("at least 35 trading days are required")
    dif = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    return bool(dif.iloc[-2] <= dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1])


def calc_kdj_cross(df: pd.DataFrame) -> bool:
    if not {"high", "low", "close"}.issubset(df.columns): raise ValueError("kline requires high, low and close")
    frame = df.loc[:, ["high", "low", "close"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(frame) < 11: raise ValueError("at least 11 trading days are required")
    low9 = frame["low"].rolling(9).min(); high9 = frame["high"].rolling(9).max()
    rsv = (frame["close"] - low9) / (high9 - low9).replace(0, pd.NA) * 100
    k = rsv.ewm(alpha=1/3, adjust=False).mean(); d = k.ewm(alpha=1/3, adjust=False).mean()
    return bool(k.iloc[-2] <= d.iloc[-2] and k.iloc[-1] > d.iloc[-1])
