"""选股条件的校验与评估函数。"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Any

Stock = dict[str, Any]
Predicate = Callable[[Stock], bool]

COMPARATORS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


def required(condition: dict[str, Any], key: str) -> Any:
    """读取必填条件字段。"""
    if key not in condition:
        raise ValueError(f"condition requires {key!r}")
    return condition[key]


def compare(field: str, op: str, value: float) -> Predicate:
    """创建数值字段比较函数。"""
    if op not in COMPARATORS:
        raise ValueError(f"unsupported comparison operator: {op!r}")
    comparator = COMPARATORS[op]
    return lambda stock: comparator(stock[field], value)


def build_predicate(condition: dict[str, Any]) -> Predicate:
    """将条件字典转换为单只股票的判断函数。"""
    if not isinstance(condition, dict):
        raise TypeError("condition must be a dict")

    condition_type = condition.get("type")
    if condition_type == "industry":
        value = str(required(condition, "value"))
        return lambda stock: value in stock["industry"]
    elif condition_type == "ma_cross_weekly":
        return lambda stock: stock["close"] >= stock["ma10_weekly"]
    elif condition_type == "ma_deviation_weekly":
        max_pct = float(required(condition, "max_pct"))
        if max_pct < 0:
            raise ValueError("max_pct must be non-negative")
        return lambda stock: abs(stock["close"] - stock["ma10_weekly"]) / stock["ma10_weekly"] * 100 <= max_pct
    elif condition_type == "rps":
        return compare("rps_250", str(required(condition, "op")), float(required(condition, "value")))
    elif condition_type == "volume_ratio":
        return compare("volume_ratio", str(required(condition, "op")), float(required(condition, "value")))
    elif condition_type == "market_cap":
        return compare("market_cap", str(required(condition, "op")), float(required(condition, "value")))
    elif condition_type == "board":
        value = str(required(condition, "value"))
        return lambda stock: stock["board"] == value
    raise ValueError(f"unsupported condition type: {condition_type!r}")
