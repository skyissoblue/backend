"""Reusable rolling operators and local OHLCV Alpha factors."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .registry import register


def ts_rank(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).apply(lambda values: pd.Series(values).rank(pct=True).iloc[-1], raw=False)


def ts_decay_linear(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1, dtype=float)
    weights /= weights.sum()
    return series.rolling(window).apply(lambda values: float(np.dot(values, weights)), raw=True)


decay_linear = ts_decay_linear


def ts_delta(series: pd.Series, period: int) -> pd.Series: return series.diff(period)
def ts_mean(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).mean()
def ts_std(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).std()
def ts_min(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).min()
def ts_max(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).max()
def ts_sum(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).sum()
def ts_product(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).apply(np.prod, raw=True)
def ts_correlation(x: pd.Series, y: pd.Series, window: int) -> pd.Series: return x.rolling(window).corr(y)
def ts_covariance(x: pd.Series, y: pd.Series, window: int) -> pd.Series: return x.rolling(window).cov(y)
def ts_argmax(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).apply(lambda x: np.argmax(x) + 1, raw=True)
def ts_argmin(series: pd.Series, window: int) -> pd.Series: return series.rolling(window).apply(lambda x: np.argmin(x) + 1, raw=True)
def ts_zscore(series: pd.Series, window: int) -> pd.Series: return (series - ts_mean(series, window)) / ts_std(series, window).replace(0, np.nan)
def rank(series: pd.Series) -> pd.Series: return series.rank(pct=True)
def scale(series: pd.Series, range: float = 1.0) -> pd.Series: return series * range / series.abs().sum()
def ts_scale(series: pd.Series) -> pd.Series: return (series - series.rolling(20).min()) / (series.rolling(20).max() - series.rolling(20).min())


def _s(df, name): return pd.to_numeric(df[name], errors="coerce")
def _vwap(df):
    if "amount" in df and (_s(df, "volume") != 0).any():
        value = _s(df, "amount") / _s(df, "volume").replace(0, np.nan)
        if value.dropna().median() > _s(df, "close").dropna().median() * 100:
            value /= 100
        return value.fillna((_s(df, "high") + _s(df, "low") + _s(df, "close")) / 3)
    return (_s(df, "high") + _s(df, "low") + _s(df, "close")) / 3


def _last(series) -> float | None:
    if len(series) == 0 or not np.isfinite(series.iloc[-1]):
        return None
    return float(series.iloc[-1])


def alpha_001(df): return _last(-ts_correlation(rank(ts_delta(np.log1p(_s(df, "volume")), 2)), rank((_s(df, "close") - _s(df, "open")) / _s(df, "open")), 6))
def alpha_002(df): return _last(-ts_decay_linear(ts_correlation(rank(_vwap(df)), rank(_s(df, "volume")), 4), 4))
def alpha_003(df): return _last(ts_rank(ts_sum(rank(_s(df, "volume")), 3), 14))
def alpha_006(df): return _last(-ts_correlation(_s(df, "open"), ts_mean(_s(df, "volume"), 10), 10))
def alpha_009(df): return _last(ts_min(ts_delta(rank(_s(df, "close")), 1), 5))
def alpha_012(df): return _last(ts_rank(ts_min(rank(_s(df, "volume")), 5), 5))
def alpha_021(df): return _last(ts_decay_linear(ts_rank(_vwap(df), 8), 8))
def alpha_023(df): return _last(ts_decay_linear(ts_rank(ts_delta(_s(df, "volume"), 3), 7), 5))
def alpha_028(df): return _last(ts_scale(ts_rank(ts_correlation(_vwap(df), ts_mean(_s(df, "volume"), 20), 12), 16)))
def alpha_054(df): return _last(-ts_delta(ts_rank(_s(df, "close"), 10), 3))
def alpha_061(df): return _last(ts_rank(ts_correlation(ts_rank(_vwap(df), 10), ts_rank(_s(df, "volume"), 10), 10), 10))
def alpha_071(df): return _last(ts_max(ts_rank(ts_correlation(ts_rank(_s(df, "close"), 10), ts_rank(_s(df, "volume"), 10), 5), 5), 3))
def alpha_101(df): return _last((_s(df, "close") - _s(df, "open")) / ((_s(df, "high") - _s(df, "low")) + 0.001))


def alpha191_01(df): return _last(-ts_correlation(rank(ts_delta(np.log1p(_s(df, "volume")), 1)), rank((_s(df, "close") - _s(df, "open")) / _s(df, "open")), 6))
def alpha191_02(df): return _last(-ts_delta(((_s(df, "close") - _s(df, "low")) - (_s(df, "high") - _s(df, "close"))) / (_s(df, "high") - _s(df, "low")).replace(0, np.nan), 1))
def alpha191_03(df): return _last(ts_sum((_s(df, "close") - _s(df, "close").shift(1)).clip(upper=0), 6))
def alpha191_04(df): return _last((ts_mean(_s(df, "close"), 8) + ts_std(_s(df, "close"), 8)) / ts_mean(_s(df, "close"), 2))
def alpha191_05(df): return _last(ts_max(ts_correlation(ts_rank(_s(df, "volume"), 5), ts_rank(_s(df, "high"), 5), 5), 3))
def alpha191_06(df): return _last(rank(np.sign(ts_delta(_s(df, "open") * 0.85 + _s(df, "high") * 0.15, 4))))
def alpha191_07(df): return _last(rank(ts_max(_vwap(df) - _s(df, "close"), 3)) + rank(ts_min(_vwap(df) - _s(df, "close"), 3)))
def alpha191_08(df): return _last(rank(ts_delta((_s(df, "high") + _s(df, "low")) * 0.1 + _vwap(df) * 0.8, 4)))
def alpha191_09(df): return _last(ts_mean(((_s(df, "high") + _s(df, "low")) / 2 - (_s(df, "high").shift(1) + _s(df, "low").shift(1)) / 2) * (_s(df, "high") - _s(df, "low")) / _s(df, "volume").replace(0, np.nan), 7))
def alpha191_10(df): return _last(ts_max(((_s(df, "close") - _s(df, "close").shift(1)).clip(lower=0)) ** 2, 20))


for number in (1, 2, 3, 6, 9, 12, 21, 23, 28, 54, 61, 71, 101):
    name = f"alpha_{number:03d}"
    register(name, "alpha", globals()[name], desc=f"Alpha101 #{number}")
for number in range(1, 11):
    name = f"alpha191_{number:02d}"
    register(name, "alpha", globals()[name], desc=f"Alpha191 #{number}")
