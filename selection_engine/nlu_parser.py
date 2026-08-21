"""Parse natural-language stock-selection instructions with OpenAI."""

from __future__ import annotations

import os
import re
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel

from .prompts import build_system_prompt


class ParsedCondition(BaseModel):
    action: Literal["add", "remove_last", "reset", "error"]
    condition: dict[str, Any] | None = None
    message: str | None = None


def _comparison(text: str) -> tuple[str, float] | None:
    match = re.search(r"(大于等于|不小于|至少|>=|大于|超过|高于|>|小于等于|不大于|至多|<=|小于|低于|<)\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    operators = {
        "大于等于": ">=", "不小于": ">=", "至少": ">=", ">=": ">=",
        "大于": ">", "超过": ">", "高于": ">", ">": ">",
        "小于等于": "<=", "不大于": "<=", "至多": "<=", "<=": "<=",
        "小于": "<", "低于": "<", "<": "<",
    }
    value = float(match.group(2))
    return operators[match.group(1)], int(value) if value.is_integer() else value


def _parse_locally(text: str) -> dict | None:
    normalized = re.sub(r"[，。！？、\s]", "", text).lower()
    if any(word in normalized for word in ("撤销", "退回", "上一步", "删掉最后")):
        return {"action": "remove_last"}
    if any(word in normalized for word in ("重置", "清空", "重新开始", "恢复全市场")):
        return {"action": "reset"}
    if "站上10周线" in normalized or "站上十周线" in normalized:
        return {"action": "add", "condition": {"type": "ma_cross_weekly"}}
    deviation = re.search(r"(?:偏离|乖离).{0,6}?(\d+(?:\.\d+)?)%?", normalized)
    if deviation and ("周线" in normalized or "10周" in normalized or "十周" in normalized):
        return {"action": "add", "condition": {"type": "ma_deviation_weekly", "max_pct": float(deviation.group(1))}}

    comparison = _comparison(normalized)
    if "rps" in normalized and comparison:
        op, value = comparison
        return {"action": "add", "condition": {"type": "rps", "op": op, "value": value}}
    if any(word in normalized for word in ("量比", "成交量")):
        op, value = comparison or (">", 1.5)
        return {"action": "add", "condition": {"type": "volume_ratio", "op": op, "value": value}}
    if "市值" in normalized and comparison:
        op, value = comparison
        multiplier = 100000000 if "亿" in normalized else 1
        return {"action": "add", "condition": {"type": "market_cap", "op": op, "value": value * multiplier}}
    if "pe" in normalized and comparison:
        op, value = comparison
        return {"action": "add", "condition": {"type": "pe", "op": op, "value": value}}
    if "macd" in normalized and any(word in normalized for word in ("金叉", "上穿")):
        return {"action": "add", "condition": {"type": "macd_cross"}}
    if "kdj" in normalized and any(word in normalized for word in ("金叉", "上穿")):
        return {"action": "add", "condition": {"type": "kdj_cross"}}
    factor_match = re.search(r"((?:alpha_?|alpha191_?)\d{1,3}|[a-z][a-z0-9_]+)", normalized)
    if factor_match and comparison:
        op, value = comparison
        raw_name = factor_match.group(1)
        if raw_name.startswith("alpha191"):
            digits = re.search(r"\d+$", raw_name).group()
            name = f"alpha191_{int(digits):02d}"
        elif raw_name.startswith("alpha"):
            digits = re.search(r"\d+$", raw_name).group()
            name = f"alpha_{int(digits):03d}"
        else:
            name = raw_name
        return {"action": "add", "condition": {"type": "factor", "name": name, "op": op, "value": value}}
    aliases = {
        "多头排列": "ma_bull_alignment", "空头排列": "ma_bear_alignment", "均线粘合": "ma_convergence",
        "macd金叉": "macd_golden_cross", "macd死叉": "macd_dead_cross", "kdj超买": "kdj_overbought",
        "kdj超卖": "kdj_oversold", "布林突破上轨": "boll_break_upper", "放量长阳": "big_yang",
        "20日新高": "new_high_20d", "二十日新高": "new_high_20d", "低波动": "low_volatility",
    }
    for phrase, name in aliases.items():
        if phrase in normalized:
            return {"action": "add", "condition": {"type": "factor", "name": name, "value": True}}

    boards = ("创业板", "科创板", "主板", "北交所")
    for board in boards:
        if board in normalized:
            return {"action": "add", "condition": {"type": "board", "value": board}}
    industry = re.search(r"([\u4e00-\u9fff]{2,8})(?:行业|股)", normalized)
    if industry:
        value = industry.group(1)
        for prefix in ("选出", "选择", "我要", "再加个", "再加"):
            value = value.removeprefix(prefix)
        if value:
            return {"action": "add", "condition": {"type": "industry", "value": value}}
    return None


def parse_condition(
    text: str,
    context_conditions: list | None = None,
) -> dict:
    if not isinstance(text, str) or not text.strip():
        return {"action": "error", "message": "text must not be empty"}

    local_result = _parse_locally(text)
    if local_result is not None:
        return local_result

    try:
        client = OpenAI()
        response = client.responses.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=[
                {
                    "role": "system",
                    "content": build_system_prompt(context_conditions),
                },
                {"role": "user", "content": text.strip()},
            ],
            text_format=ParsedCondition,
        )
        parsed = response.output_parsed
        if parsed is None:
            return {"action": "error", "message": "model returned no parsed output"}
        if isinstance(parsed, BaseModel):
            result = parsed.model_dump(exclude_none=True)
        elif isinstance(parsed, dict):
            result = parsed
        else:
            raise TypeError("unexpected OpenAI response type")
        return result
    except Exception as error:
        fallback = _parse_locally(text)
        if fallback is not None:
            return fallback
        return {"action": "error", "message": str(error)}
