"""Fast aliases plus bounded DeepSeek JSON parsing and validation."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

from openai import OpenAI as DeepSeekClient
from pydantic import BaseModel, Field, ValidationError

from factor_system.factor_lib.registry import auto_discover, get as get_factor

from .aliases import match_alias
from .prompts import CONDITION_TYPES, build_system_prompt


class NLUResult(BaseModel):
    action: Literal["add", "remove_last", "reset", "remove_specific", "replace", "error"]
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None


def _control_action(text: str) -> str | None:
    normalized = re.sub(r"\s", "", text)
    if re.search(r"撤销|退回|去掉上一步|删掉最后", normalized): return "remove_last"
    if re.search(r"重新来|重置|清空|从头|恢复全市场", normalized): return "reset"
    return None


def _normalize(condition: dict[str, Any]) -> dict[str, Any]:
    kind = str(condition.get("type", ""))
    if kind not in CONDITION_TYPES and kind not in {"board", "ma_cross_weekly", "ma_deviation_weekly"}:
        raise ValueError(f"unsupported condition type: {kind}")
    item = dict(condition)
    if kind == "board_match":
        item["type"] = "board"
    elif kind == "ma_cross" and item.get("period") == "weekly" and int(item.get("ma", 0)) == 10 and item.get("op", ">=") in {">", ">="}:
        item = {"type": "ma_cross_weekly"}
    elif kind == "ma_deviation" and item.get("period") == "weekly" and int(item.get("ma", 0)) == 10:
        item = {"type": "ma_deviation_weekly", "max_pct": float(item["max_pct"])}
    elif kind in {"alpha", "pattern"}:
        item["type"] = "factor"
    elif kind == "macd_cross":
        value = str(item.get("value", "golden")).lower()
        item = {"type": "factor", "name": "macd_dead_cross" if value in {"death", "dead", "死叉"} else "macd_golden_cross", "value": True}
    elif kind == "macd_divergence":
        item = {"type": "factor", "name": "macd_top_divergence" if str(item.get("value")) in {"top", "顶", "顶背离"} else "macd_bottom_divergence", "value": True}
    elif kind == "kdj_cross":
        item = {"type": "factor", "name": "kdj_dead_cross" if str(item.get("value")) in {"death", "dead", "死叉"} else "kdj_golden_cross", "value": True}
    elif kind == "boll":
        item = {"type": "factor", "name": "boll_break_lower" if str(item.get("value")) in {"break_lower", "lower", "下轨"} else "boll_break_upper", "value": True}
    elif kind == "rsi":
        item = {"type": "factor", "name": "rsi_6", "op": item.get("op", ">="), "value": float(item["value"])}
    if item.get("type") == "factor":
        auto_discover()
        name = str(item.get("name", ""))
        if get_factor(name) is None:
            raise ValueError(f"unknown factor: {name}")
    return item


def _finalize(payload: dict[str, Any], source: str) -> dict[str, Any]:
    if "condition" in payload and "conditions" not in payload:
        payload["conditions"] = [payload["condition"]] if payload.get("condition") else []
    parsed = NLUResult.model_validate(payload)
    conditions = [_normalize(condition) for condition in parsed.conditions]
    if parsed.action in {"add", "replace", "remove_specific"} and not conditions:
        raise ValueError(f"{parsed.action} requires conditions")
    result = parsed.model_dump(exclude_none=True)
    result["conditions"] = conditions
    result["source"] = source
    if len(conditions) == 1:
        result["condition"] = conditions[0]
    return result


def _deepseek(text: str, context: list[dict] | None) -> dict[str, Any]:
    client = DeepSeekClient(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=float(os.getenv("DEEPSEEK_TIMEOUT", "10")),
        max_retries=int(os.getenv("DEEPSEEK_MAX_RETRIES", "2")),
    )
    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        messages=[{"role": "system", "content": build_system_prompt(context)}, {"role": "user", "content": text}],
        response_format={"type": "json_object"}, max_tokens=800, temperature=0,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content
    if not content: raise ValueError("DeepSeek returned empty content")
    return json.loads(content)


def parse(text: str, context: list[dict] | None = None) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {"action": "error", "conditions": [], "message": "text must not be empty", "source": "validation"}
    action = _control_action(text)
    if action:
        return {"action": action, "conditions": [], "source": "local"}
    aliases = match_alias(text)
    if aliases:
        return _finalize({"action": "add", "conditions": aliases}, "alias")
    try:
        return _finalize(_deepseek(text.strip(), context), "deepseek")
    except (Exception, ValidationError, json.JSONDecodeError, ValueError) as error:
        fallback = match_alias(text)
        if fallback:
            return _finalize({"action": "add", "conditions": fallback}, "alias_fallback")
        return {"action": "error", "conditions": [], "message": str(error), "source": "error"}


def parse_batch(texts: list[str], context: list[dict] | None = None) -> list[dict[str, Any]]:
    if not isinstance(texts, list): raise TypeError("texts must be a list")
    return [parse(text, context) for text in texts]
