from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factor_system.factor_lib import alpha_factors, builtin_formulas, pattern_factors
from factor_system.factor_lib.registry import FACTOR_REGISTRY, auto_discover, get, list_by_kind, register, unregister


@pytest.fixture
def bars():
    rng = np.random.default_rng(7)
    close = 10 + np.cumsum(rng.normal(.02, .15, 300))
    opening = close + rng.normal(0, .05, 300)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=300), "open": opening,
        "high": np.maximum(opening, close) + .15, "low": np.minimum(opening, close) - .15,
        "close": close, "volume": rng.integers(1000, 10000, 300), "amount": close * rng.integers(1000, 10000, 300),
    })


def test_registry():
    unregister("unit_factor")
    register("unit_factor", "alpha", lambda df: 1.0)
    assert get("unit_factor")["kind"] == "alpha"
    assert "unit_factor" in list_by_kind("alpha")
    with pytest.raises(ValueError): register("unit_factor", "alpha", lambda df: 2.0)
    unregister("unit_factor")


def test_all_plugins_registered():
    auto_discover()
    assert len(FACTOR_REGISTRY) >= 100
    assert len(list_by_kind("alpha")) >= 23
    assert len(list_by_kind("pattern")) >= 30


def test_ts_rank_known_values():
    result = alpha_factors.ts_rank(pd.Series([1, 2, 3, 4, 5]), 5)
    assert result.iloc[-1] == 1.0


def test_alpha_101_formula(bars):
    expected = (bars.close.iloc[-1] - bars.open.iloc[-1]) / (bars.high.iloc[-1] - bars.low.iloc[-1] + .001)
    assert alpha_factors.alpha_101(bars) == pytest.approx(expected)


def test_pattern_outputs_bool(bars):
    assert isinstance(pattern_factors.new_high_20d(bars), bool)
    assert isinstance(pattern_factors.vol_surge(bars), bool)


def test_mmc_rsi_formula_combines_monthly_pullback_and_weekly_cross(monkeypatch, bars):
    monthly_fast = np.array([40.0, 48.0, 72.0, 75.0, 71.0])
    monthly_slow = np.array([45.0, 47.0, 55.0, 62.0, 68.0])
    weekly_fast = np.array([52.0, 61.0])
    weekly_slow = np.array([54.0, 58.0])
    pairs = iter([(monthly_fast, monthly_slow), (weekly_fast, weekly_slow)])
    monkeypatch.setattr(builtin_formulas, "talib", object())
    monkeypatch.setattr(builtin_formulas, "_rsi_pair", lambda close: next(pairs))
    assert builtin_formulas.mmc_rsi(bars) is True
