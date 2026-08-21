"""Prompt templates for natural-language condition parsing."""

from __future__ import annotations

import json
from typing import Any


SUPPORTED_TYPES = [
    "industry",
    "board",
    "ma_cross_weekly",
    "ma_deviation_weekly",
    "rps",
    "volume_ratio",
    "market_cap",
    "pe",
    "macd_cross",
    "kdj_cross",
    "factor",
]


def build_system_prompt(
    context_conditions: list[dict[str, Any]] | None = None,
) -> str:
    context = json.dumps(
        context_conditions or [],
        ensure_ascii=False,
    )
    supported = ", ".join(SUPPORTED_TYPES)
    return f"""你是 A 股选股条件解析器。把用户自然语言转换为一个结构化动作。

支持的条件类型：{supported}

规则：
1. 新增条件时 action=add，并填写 condition。
2. 用户要求撤销、删除上一步时 action=remove_last，condition=null。
3. 用户要求清空、重置、重新选股时 action=reset，condition=null。
4. 比较型条件使用 op，支持 >、>=、<、<=、==、!=。
5. “站上10周线”对应 ma_cross_weekly，不需要 op 或 value。
6. “成交量放大”默认对应 volume_ratio > 1.5；用户给出倍数时采用用户数值。
7. 无法确定时返回 action=error，并在 message 中说明原因。
8. 通用因子使用 {{"type":"factor","name":"alpha_101","op":">","value":0.5}}；布尔形态因子可省略 op，value=true。

输出示例：
{{"action":"add","condition":{{"type":"industry","value":"科技"}},"message":null}}
{{"action":"add","condition":{{"type":"rps","op":">","value":87}},"message":null}}
{{"action":"remove_last","condition":null,"message":null}}
{{"action":"reset","condition":null,"message":null}}

当前已有条件列表：{context}
只解析本次用户指令；“再加”“然后”等表达应在已有条件上新增，不要重复已有条件。"""
