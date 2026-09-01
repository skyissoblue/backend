"""Built-in stock-selection formulas exposed to the API and local NLU."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


FORMULAS: dict[str, dict[str, Any]] = {
    "mmc_rsi": {
        "name": "mmc_rsi",
        "title": "月线 RSI 回踩 + 周线 RSI 金叉",
        "description": (
            "月线 RSI6 上穿 RSI12 后曾达到 70，当前 RSI6 回踩但不跌破 RSI12，"
            "同时周线 RSI6 当期上穿 RSI12"
        ),
        "condition": {"type": "factor", "name": "mmc_rsi", "value": True},
    },
}


def get_formula(name: str) -> dict[str, Any] | None:
    formula = FORMULAS.get(name.strip().lower())
    return deepcopy(formula) if formula else None


def list_formulas() -> list[dict[str, Any]]:
    return [deepcopy(FORMULAS[name]) for name in sorted(FORMULAS)]

