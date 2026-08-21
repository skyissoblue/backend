"""Progressive stock-selection session using live AkShare data."""
from __future__ import annotations
import os
from copy import deepcopy
from typing import Any
from . import data_provider, indicators
from . import database
from .cache import create_cache
from .conditions import COMPARATORS, required
from .mock_data import generate_mock_market

try:
    from factor_system import redis_store as factor_store
    from factor_system.factor_lib.registry import auto_discover as discover_factors, get as get_factor_definition
except ImportError:
    factor_store = None
    discover_factors = None
    get_factor_definition = None

class SelectionSession:
    def __init__(self, limit: int | None = None) -> None:
        self._data_mode = os.getenv("SELECTION_ENGINE_DATA_MODE", "real").lower()
        self._mock_mode = self._data_mode == "mock"
        if self._mock_mode:
            stocks = generate_mock_market()
            self._universe = stocks[:limit] if limit is not None else stocks
        elif self._data_mode == "local":
            self._universe = database.load_stocks(limit)
            if not self._universe:
                raise RuntimeError("local stock database is empty; run the market data pipeline first")
        else:
            stocks = data_provider.get_all_stocks()
            if limit is not None:
                if limit < 0: raise ValueError("limit must be non-negative")
                stocks = stocks.head(limit)
            self._universe = stocks.loc[:, ["code", "name"]].to_dict("records")
        self._conditions: list[dict[str, Any]] = []
        self._stocks = list(self._universe)
        self._cache = create_cache()
        self._all_closes: dict[str, Any] | None = None
        self._factor_values: dict[str, dict[str, Any]] = {}

    @property
    def stocks(self) -> list[dict[str, Any]]: return deepcopy(self._stocks)

    @property
    def conditions(self) -> list[dict[str, Any]]: return deepcopy(self._conditions)

    def apply_condition(self, condition: dict) -> dict:
        self._validate_condition(condition)
        if condition.get("type") == "factor" and self._data_mode == "local" and factor_store is not None:
            name = str(condition["name"])
            if name not in self._factor_values:
                self._factor_values[name] = factor_store.batch_get_factor([stock["code"] for stock in self._universe], name)
        before = len(self._stocks)
        self._stocks = [stock for stock in self._stocks if self._matches(stock, condition)]
        self._conditions.append(deepcopy(condition))
        return self._result(before)

    def remove_last(self) -> dict:
        before = len(self._stocks)
        if self._conditions:
            self._conditions.pop(); self._recalculate()
        return self._result(before)

    def reset(self) -> dict:
        before = len(self._stocks)
        self._conditions.clear(); self._stocks = list(self._universe)
        return self._result(before)

    def _kline(self, code: str): return self._cache.get_or_calc(code, data_provider.get_daily_kline, code)
    def _info(self, code: str): return self._cache.get_or_calc(code, data_provider.get_stock_info, code)
    def _indicator(self, code: str, func, *args): return self._cache.get_or_calc(code, func, *args)

    def _get_all_closes(self) -> dict[str, Any]:
        if self._all_closes is None:
            self._all_closes = {stock["code"]: self._kline(stock["code"])["close"] for stock in self._universe}
        return self._all_closes

    def _matches(self, stock: dict[str, Any], condition: dict) -> bool:
        code, kind = stock["code"], condition["type"]
        if self._mock_mode:
            if kind == "industry": return str(required(condition, "value")) in stock["industry"]
            elif kind == "board": return stock["board"] == str(required(condition, "value"))
            elif kind == "ma_cross_weekly": return stock["close"] >= stock["ma10_weekly"]
            elif kind == "ma_deviation_weekly": return abs(stock["close"] - stock["ma10_weekly"]) / stock["ma10_weekly"] * 100 <= float(required(condition, "max_pct"))
            elif kind in {"rps", "volume_ratio", "market_cap", "pe"}: return self._compare(float(stock[{"rps":"rps_250"}.get(kind, kind)]), condition)
            elif kind in {"macd_cross", "kdj_cross"}: return False
            elif kind == "factor": return False
        if self._data_mode == "local":
            if kind == "industry": return str(required(condition, "value")) in str(stock.get("industry") or "")
            elif kind == "board": return stock.get("board") == str(required(condition, "value"))
            elif kind == "ma_cross_weekly":
                return self._has(stock, "close", "weekly_ma10") and float(stock["close"]) >= float(stock["weekly_ma10"])
            elif kind == "ma_deviation_weekly":
                return self._has(stock, "weekly_deviation") and abs(float(stock["weekly_deviation"])) <= float(required(condition, "max_pct"))
            elif kind == "rps": return self._stored_compare(stock, "rps_250", condition)
            elif kind == "volume_ratio": return self._stored_compare(stock, "volume_ratio", condition)
            elif kind == "market_cap": return self._stored_compare(stock, "market_cap", condition)
            elif kind == "pe": return self._stored_compare(stock, "pe", condition)
            elif kind in {"macd_cross", "kdj_cross"}: return False
            elif kind == "factor":
                if factor_store is None: return False
                name = str(required(condition, "name"))
                value = self._factor_values.get(name, {}).get(code)
                if value is None and name not in self._factor_values:
                    value = factor_store.get_factor(code, name)
                if value is None: return False
                if "op" not in condition: return bool(value) == bool(condition.get("value", True))
                return self._compare(float(value), condition)
        if kind == "industry": return str(required(condition, "value")) in self._info(code)["industry"]
        elif kind == "board": return self._info(code)["board"] == str(required(condition, "value"))
        elif kind == "ma_cross_weekly":
            kline = self._kline(code)
            return float(kline["close"].iloc[-1]) >= self._indicator(code, indicators.calc_weekly_ma10, kline)
        elif kind == "ma_deviation_weekly":
            return abs(self._indicator(code, indicators.calc_ma_deviation_weekly, self._kline(code))) <= float(required(condition, "max_pct"))
        elif kind == "rps": return self._compare(self._indicator(code, indicators.calc_rps_250, code, self._get_all_closes()), condition)
        elif kind == "volume_ratio": return self._compare(self._indicator(code, indicators.calc_volume_ratio, self._kline(code)), condition)
        elif kind == "market_cap":
            value = self._info(code)["market_cap"]
            return value is not None and self._compare(float(value), condition)
        elif kind == "pe":
            value = self._info(code)["pe"]
            return value is not None and self._compare(float(value), condition)
        elif kind == "macd_cross":
            return self._indicator(code, indicators.calc_macd_cross, self._kline(code))
        elif kind == "kdj_cross":
            return self._indicator(code, indicators.calc_kdj_cross, self._kline(code))
        elif kind == "factor":
            raise ValueError("factor conditions require local data mode")
        raise ValueError(f"unsupported condition type: {kind!r}")

    @staticmethod
    def _has(stock: dict[str, Any], *fields: str) -> bool:
        return all(stock.get(field) is not None for field in fields)

    def _stored_compare(self, stock: dict[str, Any], field: str, condition: dict) -> bool:
        value = stock.get(field)
        return value is not None and self._compare(float(value), condition)

    @staticmethod
    def _compare(actual: float, condition: dict) -> bool:
        op = str(required(condition, "op"))
        if op not in COMPARATORS: raise ValueError(f"unsupported comparison operator: {op!r}")
        return COMPARATORS[op](actual, float(required(condition, "value")))

    @staticmethod
    def _validate_condition(condition: dict) -> None:
        if not isinstance(condition, dict): raise TypeError("condition must be a dict")
        kind = condition.get("type")
        if kind not in {"industry", "board", "ma_cross_weekly", "ma_deviation_weekly", "rps", "volume_ratio", "market_cap", "pe", "macd_cross", "kdj_cross", "factor"}: raise ValueError(f"unsupported condition type: {kind!r}")
        if kind in {"industry", "board"}: required(condition, "value")
        elif kind == "ma_deviation_weekly":
            if float(required(condition, "max_pct")) < 0: raise ValueError("max_pct must be non-negative")
        elif kind in {"rps", "volume_ratio", "market_cap", "pe"}:
            op = str(required(condition, "op")); required(condition, "value")
            if op not in COMPARATORS: raise ValueError(f"unsupported comparison operator: {op!r}")
        elif kind == "factor":
            name = str(required(condition, "name"))
            if discover_factors is None or get_factor_definition is None:
                raise ValueError("factor system is unavailable")
            discover_factors()
            if get_factor_definition(name) is None: raise ValueError(f"unknown factor: {name}")
            if "op" in condition:
                op = str(condition["op"]); required(condition, "value")
                if op not in COMPARATORS: raise ValueError(f"unsupported comparison operator: {op!r}")

    def _recalculate(self) -> None:
        stocks = list(self._universe)
        for condition in self._conditions: stocks = [stock for stock in stocks if self._matches(stock, condition)]
        self._stocks = stocks

    def _result(self, before: int) -> dict:
        after = len(self._stocks)
        return {"before":before, "after":after, "removed":max(before-after, 0), "stocks":self.stocks}
