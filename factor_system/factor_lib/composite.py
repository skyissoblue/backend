"""Factor combination helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .registry import get


def normalize(series: pd.Series) -> pd.Series:
    low, high = series.min(), series.max()
    return pd.Series(0.5, index=series.index) if high == low else (series - low) / (high - low)


def combine(factor_names: list[str], weights: list[float] | None = None):
    weights = weights or [1 / len(factor_names)] * len(factor_names)
    if len(weights) != len(factor_names):
        raise ValueError("weights and factors must have equal length")
    def calculate(df):
        values = []
        for name in factor_names:
            item = get(name)
            if item is None: raise ValueError(f"unknown factor: {name}")
            value = item["func"](df)
            values.append(value.get(name) if isinstance(value, dict) else value)
        return None if any(value is None for value in values) else float(np.dot(values, weights))
    return calculate


def rank_combine(factor_names: list[str]):
    return combine(factor_names)
