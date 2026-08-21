"""Latest-bar technical structure and pattern factors."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .registry import register

try:
    import talib
except ImportError:
    talib = None


def _a(df, field): return np.asarray(pd.to_numeric(df[field], errors="coerce"), dtype="float64")
def _ready(df, length): return len(df) >= length and talib is not None
def _last(array): return None if len(array) == 0 or not math.isfinite(float(array[-1])) else float(array[-1])
def _ma(df, period): return talib.SMA(_a(df, "close"), period) if _ready(df, period) else np.array([np.nan])


def ma_bull_alignment(df):
    values = [_last(_ma(df, n)) for n in (5, 10, 20, 60)]
    return None if None in values else values[0] > values[1] > values[2] > values[3]


def ma_bear_alignment(df):
    values = [_last(_ma(df, n)) for n in (5, 10, 20, 60)]
    return None if None in values else values[0] < values[1] < values[2] < values[3]


def ma_convergence(df):
    values = [_last(_ma(df, n)) for n in (5, 10, 20, 60)]
    return None if None in values else (max(values) - min(values)) / (sum(values) / 4) < 0.02


def ma_angle_ma10(df):
    ma = _ma(df, 10)
    return None if len(ma) < 6 or not np.isfinite(ma[-6]) else float(np.degrees(np.arctan((ma[-1] - ma[-6]) / 5 / ma[-6])))


def _macd(df): return talib.MACD(_a(df, "close"), 12, 26, 9) if _ready(df, 35) else (np.array([]),) * 3
def macd_golden_cross(df):
    dif, dea, _ = _macd(df); return None if len(dif) < 2 else bool(dif[-2] <= dea[-2] and dif[-1] > dea[-1])
def macd_dead_cross(df):
    dif, dea, _ = _macd(df); return None if len(dif) < 2 else bool(dif[-2] >= dea[-2] and dif[-1] < dea[-1])
def macd_red_expand(df):
    *_, hist = _macd(df); return None if len(hist) < 2 else bool(hist[-1] > hist[-2] > 0)
def macd_green_shrink(df):
    *_, hist = _macd(df); return None if len(hist) < 2 else bool(hist[-2] < hist[-1] < 0)
def macd_top_divergence(df):
    *_, hist = _macd(df); close = _a(df, "close"); return None if len(hist) < 60 else bool(close[-1] >= np.nanmax(close[-60:]) and hist[-1] < np.nanmax(hist[-60:-1]))
def macd_bottom_divergence(df):
    *_, hist = _macd(df); close = _a(df, "close"); return None if len(hist) < 60 else bool(close[-1] <= np.nanmin(close[-60:]) and hist[-1] > np.nanmin(hist[-60:-1]))


def _kdj(df): return talib.STOCH(_a(df, "high"), _a(df, "low"), _a(df, "close")) if _ready(df, 20) else (np.array([]), np.array([]))
def kdj_golden_cross(df):
    k, d = _kdj(df); return None if len(k) < 2 else bool(k[-2] <= d[-2] and k[-1] > d[-1])
def kdj_dead_cross(df):
    k, d = _kdj(df); return None if len(k) < 2 else bool(k[-2] >= d[-2] and k[-1] < d[-1])
def kdj_overbought(df):
    k, _ = _kdj(df); return None if not len(k) else bool(k[-1] > 80)
def kdj_oversold(df):
    k, _ = _kdj(df); return None if not len(k) else bool(k[-1] < 20)
def rsi_overbought(df): return None if not _ready(df, 7) else bool(talib.RSI(_a(df, "close"), 6)[-1] > 70)
def rsi_oversold(df): return None if not _ready(df, 7) else bool(talib.RSI(_a(df, "close"), 6)[-1] < 30)


def _boll(df): return talib.BBANDS(_a(df, "close"), 20, 2, 2) if _ready(df, 20) else (np.array([]),) * 3
def boll_break_upper(df):
    upper, _, _ = _boll(df); return None if not len(upper) else bool(_a(df, "close")[-1] > upper[-1])
def boll_break_lower(df):
    _, _, lower = _boll(df); return None if not len(lower) else bool(_a(df, "close")[-1] < lower[-1])
def boll_position(df):
    upper, _, lower = _boll(df); return None if not len(upper) or upper[-1] == lower[-1] else float((_a(df, "close")[-1] - lower[-1]) / (upper[-1] - lower[-1]))
def boll_squeeze(df):
    upper, middle, lower = _boll(df)
    if len(upper) < 250: return None
    width = (upper - lower) / middle
    return bool(width[-1] <= np.nanpercentile(width[-250:], 20))


def vol_continuous_up(df, n=3):
    volume = _a(df, "volume"); return None if len(volume) < n else bool(np.all(np.diff(volume[-n:]) > 0))
def vol_continuous_down(df, n=3):
    volume = _a(df, "volume"); return None if len(volume) < n else bool(np.all(np.diff(volume[-n:]) < 0))
def vol_surge(df):
    volume = _a(df, "volume"); return None if len(volume) < 6 else bool(volume[-1] > np.mean(volume[-6:-1]) * 3)
def vol_dry(df):
    volume = _a(df, "volume"); return None if len(volume) < 6 else bool(volume[-1] < np.mean(volume[-6:-1]) * .5)
def big_yang(df):
    close, volume = _a(df, "close"), _a(df, "volume"); return None if len(df) < 6 else bool(close[-1] / close[-2] - 1 > .03 and volume[-1] / np.mean(volume[-6:-1]) > 2)
def doji(df):
    opening, close = _a(df, "open")[-1], _a(df, "close")[-1]; return bool(abs(close - opening) / opening < .01)
def hammer(df):
    opening, high, low, close = (_a(df, name)[-1] for name in ("open", "high", "low", "close")); body = max(abs(close - opening), 1e-9); return bool(min(opening, close) - low > body * 2 and high - max(opening, close) < body)
def new_high_20d(df):
    close = _a(df, "close"); return None if len(close) < 20 else bool(close[-1] >= np.max(close[-20:]))
def new_low_20d(df):
    close = _a(df, "close"); return None if len(close) < 20 else bool(close[-1] <= np.min(close[-20:]))
def breakout_prev_high(df):
    close, high = _a(df, "close"), _a(df, "high"); return None if len(close) < 21 else bool(close[-1] > np.max(high[-21:-1]))
def pullback_support(df):
    close = _a(df, "close"); return None if len(close) < 21 else bool(.05 <= 1 - close[-1] / np.max(close[-21:-1]) <= .10 and close[-1] >= close[-2])
def low_volatility(df): return None if not _ready(df, 15) else bool(talib.ATR(_a(df, "high"), _a(df, "low"), _a(df, "close"), 14)[-1] / _a(df, "close")[-1] < .02)
def high_volatility(df): return None if not _ready(df, 15) else bool(talib.ATR(_a(df, "high"), _a(df, "low"), _a(df, "close"), 14)[-1] / _a(df, "close")[-1] > .05)


_FACTORS = [
    ma_bull_alignment, ma_bear_alignment, ma_convergence, ma_angle_ma10,
    macd_golden_cross, macd_dead_cross, macd_red_expand, macd_green_shrink, macd_top_divergence, macd_bottom_divergence,
    kdj_golden_cross, kdj_dead_cross, kdj_overbought, kdj_oversold, rsi_overbought, rsi_oversold,
    boll_break_upper, boll_break_lower, boll_squeeze, boll_position,
    vol_continuous_up, vol_continuous_down, vol_surge, vol_dry, big_yang, doji, hammer,
    new_high_20d, new_low_20d, breakout_prev_high, pullback_support, low_volatility, high_volatility,
]
for function in _FACTORS:
    register(function.__name__, "pattern", function, desc=function.__name__)
