"""TA-Lib-backed technical factors; no indicator formulas are reimplemented here."""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from .registry import register

try:
    import talib
except ImportError:  # Registry remains inspectable before the optional native wheel is installed.
    talib = None


def _arrays(df):
    return tuple(np.asarray(df[name], dtype="float64") for name in ("open", "high", "low", "close", "volume"))


def _last(value):
    if value is None or len(value) == 0 or not np.isfinite(value[-1]):
        return None
    return float(value[-1])


def _single(function: str, inputs: tuple[str, ...], **kwargs) -> Callable:
    def calculate(df):
        if talib is None:
            return None
        values = [np.asarray(df[column], dtype="float64") for column in inputs]
        return _last(getattr(talib, function)(*values, **kwargs))
    return calculate


for period in (5, 10, 20, 60, 120, 250):
    register(f"ma_{period}", "ta", _single("SMA", ("close",), timeperiod=period), desc=f"{period}日简单均线")
for function, periods in {
    "EMA": (12, 26, 50, 200), "WMA": (10, 20, 60), "DEMA": (10, 20, 60),
    "TEMA": (10, 20, 60), "TRIMA": (10, 20, 60), "KAMA": (10, 20, 30), "T3": (5, 10, 20),
}.items():
    for period in periods:
        register(f"{function.lower()}_{period}", "ta", _single(function, ("close",), timeperiod=period), desc=f"{function}({period})")

for name, function, inputs, kwargs in (
    ("adx_14", "ADX", ("high", "low", "close"), {"timeperiod": 14}),
    ("adxr_14", "ADXR", ("high", "low", "close"), {"timeperiod": 14}),
    ("plus_di_14", "PLUS_DI", ("high", "low", "close"), {"timeperiod": 14}),
    ("minus_di_14", "MINUS_DI", ("high", "low", "close"), {"timeperiod": 14}),
    ("plus_dm_14", "PLUS_DM", ("high", "low"), {"timeperiod": 14}),
    ("minus_dm_14", "MINUS_DM", ("high", "low"), {"timeperiod": 14}),
    ("aroonosc_14", "AROONOSC", ("high", "low"), {"timeperiod": 14}),
    ("cci_14", "CCI", ("high", "low", "close"), {"timeperiod": 14}),
    ("trix_14", "TRIX", ("close",), {"timeperiod": 14}),
    ("dx_14", "DX", ("high", "low", "close"), {"timeperiod": 14}),
    ("willr_14", "WILLR", ("high", "low", "close"), {"timeperiod": 14}),
    ("cmo_14", "CMO", ("close",), {"timeperiod": 14}),
    ("mfi_14", "MFI", ("high", "low", "close", "volume"), {"timeperiod": 14}),
    ("ultosc", "ULTOSC", ("high", "low", "close"), {}),
    ("bop", "BOP", ("open", "high", "low", "close"), {}),
    ("atr_14", "ATR", ("high", "low", "close"), {"timeperiod": 14}),
    ("natr_14", "NATR", ("high", "low", "close"), {"timeperiod": 14}),
    ("trange", "TRANGE", ("high", "low", "close"), {}),
    ("obv", "OBV", ("close", "volume"), {}),
    ("ad", "AD", ("high", "low", "close", "volume"), {}),
    ("adosc", "ADOSC", ("high", "low", "close", "volume"), {}),
    ("ht_trendline", "HT_TRENDLINE", ("close",), {}),
    ("ht_trendmode", "HT_TRENDMODE", ("close",), {}),
    ("ht_dcperiod", "HT_DCPERIOD", ("close",), {}),
    ("ht_dcphase", "HT_DCPHASE", ("close",), {}),
    ("sar", "SAR", ("high", "low"), {}),
    ("sarext", "SAREXT", ("high", "low"), {}),
    ("midpoint_14", "MIDPOINT", ("close",), {"timeperiod": 14}),
    ("midprice_14", "MIDPRICE", ("high", "low"), {"timeperiod": 14}),
    ("stddev_20", "STDDEV", ("close",), {"timeperiod": 20}),
    ("var_20", "VAR", ("close",), {"timeperiod": 20}),
):
    register(name, "ta", _single(function, inputs, **kwargs), desc=name)

for period in (6, 12, 24):
    register(f"rsi_{period}", "ta", _single("RSI", ("close",), timeperiod=period), desc=f"RSI({period})")
for period in (10, 20):
    for function in ("ROC", "ROCR", "ROCP"):
        register(f"{function.lower()}_{period}", "ta", _single(function, ("close",), timeperiod=period), desc=f"{function}({period})")

for name, function, inputs, kwargs in (
    ("mom_10", "MOM", ("close",), {"timeperiod": 10}),
    ("apo", "APO", ("close",), {}), ("ppo", "PPO", ("close",), {}),
    ("beta_5", "BETA", ("high", "low"), {"timeperiod": 5}),
    ("correl_30", "CORREL", ("high", "low"), {"timeperiod": 30}),
    ("linearreg_14", "LINEARREG", ("close",), {"timeperiod": 14}),
    ("linearreg_angle_14", "LINEARREG_ANGLE", ("close",), {"timeperiod": 14}),
    ("linearreg_intercept_14", "LINEARREG_INTERCEPT", ("close",), {"timeperiod": 14}),
    ("linearreg_slope_14", "LINEARREG_SLOPE", ("close",), {"timeperiod": 14}),
    ("tsf_14", "TSF", ("close",), {"timeperiod": 14}),
    ("avgprice", "AVGPRICE", ("open", "high", "low", "close"), {}),
    ("medprice", "MEDPRICE", ("high", "low"), {}),
    ("typprice", "TYPPRICE", ("high", "low", "close"), {}),
    ("wclprice", "WCLPRICE", ("high", "low", "close"), {}),
):
    register(name, "ta", _single(function, inputs, **kwargs), desc=name)


def macd(df):
    if talib is None:
        return {}
    _, _, hist = talib.MACD(np.asarray(df["close"], dtype="float64"), 12, 26, 9)
    return {"macd_hist": _last(hist)}


def boll(df):
    if talib is None:
        return {}
    close = np.asarray(df["close"], dtype="float64")
    upper, middle, lower = talib.BBANDS(close, 20, 2, 2)
    u, m, l, c = _last(upper), _last(middle), _last(lower), float(close[-1])
    width = None if None in (u, m, l) or m == 0 else (u - l) / m
    position = None if None in (u, l) or u == l else (c - l) / (u - l)
    return {"boll_upper": u, "boll_middle": m, "boll_lower": l, "boll_width": width, "boll_position": position}


def kdj(df):
    if talib is None:
        return {}
    _, high, low, close, _ = _arrays(df)
    k, d = talib.STOCH(high, low, close)
    return {"kdj_k": _last(k), "kdj_d": _last(d), "kdj_j": None if _last(k) is None or _last(d) is None else 3 * _last(k) - 2 * _last(d)}


def aroon(df):
    if talib is None:
        return {}
    _, high, low, _, _ = _arrays(df)
    down, up = talib.AROON(high, low, 14)
    return {"aroon_down": _last(down), "aroon_up": _last(up)}


def ht_sine(df):
    if talib is None:
        return {}
    sine, lead = talib.HT_SINE(np.asarray(df["close"], dtype="float64"))
    return {"ht_sine": _last(sine), "ht_leadsine": _last(lead)}


def ht_phasor(df):
    if talib is None:
        return {}
    phase, quadrature = talib.HT_PHASOR(np.asarray(df["close"], dtype="float64"))
    return {"ht_inphase": _last(phase), "ht_quadrature": _last(quadrature)}


register("macd", "ta", macd, ["macd_hist"], "MACD柱")
register("boll", "ta", boll, ["boll_upper", "boll_middle", "boll_lower", "boll_width", "boll_position"], "布林带")
register("kdj", "ta", kdj, ["kdj_k", "kdj_d", "kdj_j"], "KDJ")
register("aroon", "ta", aroon, ["aroon_down", "aroon_up"], "AROON")
register("ht_sine_pair", "ta", ht_sine, ["ht_sine", "ht_leadsine"], "Hilbert正弦")
register("ht_phasor_pair", "ta", ht_phasor, ["ht_inphase", "ht_quadrature"], "Hilbert相量")


def vwap(df):
    volume = np.asarray(df["volume"], dtype="float64")
    typical = (np.asarray(df["high"], dtype="float64") + np.asarray(df["low"], dtype="float64") + np.asarray(df["close"], dtype="float64")) / 3
    denominator = np.nansum(volume)
    return None if denominator == 0 else float(np.nansum(typical * volume) / denominator)


register("vwap", "ta", vwap, desc="全区间成交量加权均价")

# TA-Lib exposes its complete, well-tested candlestick-recognition family. Each
# function is independently addressable in the registry and returns the latest
# signal (-100/0/100, occasionally +/-200).
_CANDLE_PATTERNS = (
    "CDL2CROWS CDL3BLACKCROWS CDL3INSIDE CDL3LINESTRIKE CDL3OUTSIDE CDL3STARSINSOUTH "
    "CDL3WHITESOLDIERS CDLABANDONEDBABY CDLADVANCEBLOCK CDLBELTHOLD CDLBREAKAWAY "
    "CDLCLOSINGMARUBOZU CDLCONCEALBABYSWALL CDLCOUNTERATTACK CDLDARKCLOUDCOVER CDLDOJI "
    "CDLDOJISTAR CDLDRAGONFLYDOJI CDLENGULFING CDLEVENINGDOJISTAR CDLEVENINGSTAR "
    "CDLGAPSIDESIDEWHITE CDLGRAVESTONEDOJI CDLHAMMER CDLHANGINGMAN CDLHARAMI "
    "CDLHARAMICROSS CDLHIGHWAVE CDLHIKKAKE CDLHIKKAKEMOD CDLHOMINGPIGEON "
    "CDLIDENTICAL3CROWS CDLINNECK CDLINVERTEDHAMMER CDLKICKING CDLKICKINGBYLENGTH "
    "CDLLADDERBOTTOM CDLLONGLEGGEDDOJI CDLLONGLINE CDLMARUBOZU CDLMATCHINGLOW "
    "CDLMATHOLD CDLMORNINGDOJISTAR CDLMORNINGSTAR CDLONNECK CDLPIERCING CDLRICKSHAWMAN "
    "CDLRISEFALL3METHODS CDLSEPARATINGLINES CDLSHOOTINGSTAR CDLSHORTLINE CDLSPINNINGTOP "
    "CDLSTALLEDPATTERN CDLSTICKSANDWICH CDLTAKURI CDLTASUKIGAP CDLTHRUSTING "
    "CDLTRISTAR CDLUNIQUE3RIVER CDLUPSIDEGAP2CROWS CDLXSIDEGAP3METHODS"
).split()
for function in _CANDLE_PATTERNS:
    register(f"pattern_{function[3:].lower()}", "ta", _single(function, ("open", "high", "low", "close")), desc=f"TA-Lib {function}")
