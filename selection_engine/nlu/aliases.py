"""Fast deterministic aliases used when DeepSeek is unavailable or uncertain."""
from __future__ import annotations

import re
from typing import Any

from factor_system.factor_lib.registry import auto_discover, get as get_factor

FACTOR_ALIASES = {
    "创业板": [("创业板", 1.0), ("3开头", 1.0), ("300开头", 1.0), ("301开头", 1.0)],
    "科创板": [("科创板", 1.0), ("科创", .9), ("688开头", 1.0)],
    "主板": [("主板", 1.0), ("60开头", 1.0), ("00开头", 1.0)],
    "北交所": [("北交所", 1.0), ("北交", .9), ("8开头", 1.0), ("4开头", 1.0)],
    "macd_top_divergence": [("MACD顶背离", 1.0), ("顶背离", 1.0), ("顶背了", 1.0)],
    "macd_bottom_divergence": [("MACD底背离", 1.0), ("底背离", 1.0), ("底背了", 1.0)],
    "macd_golden_cross": [("MACD金叉", 1.0), ("MACD翻红", 1.0), ("DIF上穿DEA", 1.0)],
    "macd_dead_cross": [("MACD死叉", 1.0), ("MACD翻绿", 1.0), ("DIF下穿DEA", 1.0)],
    "rsi_overbought": [("RSI超买", 1.0), ("RSI大于70", 1.0)],
    "rsi_oversold": [("RSI超卖", 1.0), ("RSI小于30", 1.0)],
    "rps_high": [("强势", 1.0), ("涨得好", .8), ("近期强", .8)],
    "rps_low": [("低位", 1.0), ("底部", 1.0), ("超跌", 1.0)],
    "volume_high": [("放量", 1.0), ("巨量", 1.0), ("成交量放大", 1.0)],
    "volume_low": [("缩量", 1.0), ("地量", 1.0), ("成交量萎缩", 1.0)],
}


def _comparison(text: str, label: str) -> tuple[str, float] | None:
    escaped = re.escape(label)
    match = re.search(escaped + r".{0,6}?(大于等于|不小于|至少|>=|以上|大于|超过|高于|>|小于等于|不大于|至多|<=|以下|小于|低于|<)\s*(\d+(?:\.\d+)?)", text, re.I)
    if not match:
        return None
    operators = {"大于等于": ">=", "不小于": ">=", "至少": ">=", ">=": ">=", "以上": ">=", "大于": ">", "超过": ">", "高于": ">", ">": ">", "小于等于": "<=", "不大于": "<=", "至多": "<=", "<=": "<=", "以下": "<=", "小于": "<", "低于": "<", "<": "<"}
    return operators[match.group(1)], float(match.group(2))


def match_alias(text: str) -> list[dict[str, Any]]:
    normalized = re.sub(r"[，。！？、；;\s]", "", text)
    conditions: list[tuple[float, dict[str, Any]]] = []

    for board, aliases in list(FACTOR_ALIASES.items())[:4]:
        confidence = max((score for phrase, score in aliases if phrase.lower() in normalized.lower()), default=0)
        if confidence:
            conditions.append((confidence, {"type": "board", "value": board}))
            break
    if re.search(r"(排除|不要|去掉|非)\*?ST|去掉垃圾股", normalized, re.I):
        conditions.append((1.0, {"type": "exclude_st", "value": True}))

    period_names = {"日": "daily", "周": "weekly", "月": "monthly", "年": "yearly"}
    # In Chinese stock-market terminology, an unqualified "年线" means the
    # 250-trading-day moving average, not a one-year-period moving average.
    if re.search(r"(?:跌破|低于)年线|年线(?:以下|下方)", normalized):
        conditions.append((1.0, {"type": "ma_cross", "period": "daily", "ma": 250, "op": "<"}))
    elif re.search(r"(?:站上|突破|高于)年线|(?:在|位于|处于)?年线(?:以上|上方)", normalized):
        conditions.append((1.0, {"type": "ma_cross", "period": "daily", "ma": 250, "op": ">="}))
    standing = re.search(r"(?:站上|高于|在|(?:股价|价格)上穿)(\d+|十|二十)(日|周|月|年)(?:线|均线)|(?:跌破|低于)(\d+|十|二十)(日|周|月|年)(?:线|均线)", normalized, re.I)
    if standing:
        above_value, above_period, below_value, below_period = standing.groups()
        raw = above_value or below_value
        window = {"十": 10, "二十": 20}.get(raw, int(raw) if raw and raw.isdigit() else 10)
        conditions.append((1.0, {"type": "ma_cross", "period": period_names[above_period or below_period], "ma": window, "op": ">=" if above_value else "<"}))
    reverse = re.search(r"(日|周|月|年)(?:线|均线)MA?(\d+)(?:以上|上方)", normalized, re.I)
    if reverse:
        conditions.append((1.0, {"type": "ma_cross", "period": period_names[reverse.group(1)], "ma": int(reverse.group(2)), "op": ">="}))
    cross = re.search(r"(?:MA)?(\d+)(日|周|月|年)(?:均线|线)(金叉|上穿|死叉|下穿)(?:MA)?(\d+)(?:日|周|月|年)(?:均线|线)", normalized, re.I)
    if cross:
        conditions.append((1.0, {"type": "ma_cross", "period": period_names[cross.group(2)], "ma_fast": int(cross.group(1)), "ma_slow": int(cross.group(4)), "cross": "death" if cross.group(3) in {"死叉", "下穿"} else "golden"}))
    deviation = re.search(r"(?:偏离|乖离)(\d+)(日|周|月|年)(?:线|均线).{0,8}?(\d+(?:\.\d+)?)%?", normalized)
    if deviation:
        conditions.append((1.0, {"type": "ma_deviation", "period": period_names[deviation.group(2)], "ma": int(deviation.group(1)), "max_pct": float(deviation.group(3))}))

    rps_front = re.search(r"RPS(?:排名)?前(\d+(?:\.\d+)?)%", normalized, re.I)
    rps = _comparison(normalized, "RPS")
    if rps_front:
        conditions.append((1.0, {"type": "rps", "op": ">=", "value": 100 - float(rps_front.group(1))}))
    elif rps:
        conditions.append((1.0, {"type": "rps", "op": rps[0], "value": rps[1]}))
    elif re.search(r"涨得好|强势|近期强", normalized):
        conditions.append((.9, {"type": "rps", "op": ">=", "value": 80}))
    elif re.search(r"低位|底部|超跌|跌多了", normalized):
        conditions.append((.9, {"type": "rps", "op": "<=", "value": 30 if "启动" in normalized else 20}))

    volume = _comparison(normalized, "量比")
    if volume:
        conditions.append((1.0, {"type": "volume_ratio", "op": volume[0], "value": volume[1]}))
    elif re.search(r"放量|巨量|成交量放大", normalized):
        conditions.append((.9, {"type": "volume_ratio", "op": ">=", "value": 2}))
    elif re.search(r"缩量|地量|成交量萎缩", normalized):
        conditions.append((.9, {"type": "volume_ratio", "op": "<=", "value": .8}))
    elif re.search(r"热门|资金关注|活跃", normalized):
        conditions.append((.8, {"type": "volume_ratio", "op": ">=", "value": 1.5}))
    if "低位启动" in normalized and not re.search(r"放量|巨量|成交量放大", normalized):
        conditions.append((.9, {"type": "volume_ratio", "op": ">=", "value": 2}))
    continuous = re.search(r"连续(\d+)天放量", normalized)
    if continuous:
        conditions.append((1.0, {"type": "factor", "name": "vol_continuous_up", "value": True, "params": {"days": int(continuous.group(1))}}))

    market_cap = _comparison(normalized, "市值")
    if market_cap:
        multiplier = 100_000_000 if "亿" in normalized else 1
        conditions.append((1.0, {"type": "market_cap", "op": market_cap[0], "value": market_cap[1] * multiplier}))
    elif re.search(r"大盘股|大票|权重", normalized):
        conditions.append((.9, {"type": "market_cap", "op": ">=", "value": 50_000_000_000}))
    elif re.search(r"小盘股|小票|迷你盘", normalized):
        conditions.append((.9, {"type": "market_cap", "op": "<=", "value": 5_000_000_000}))
    if re.search(r"估值合理|估值不高|不过分昂贵|不贵", normalized):
        conditions.extend([(1.0, {"type": "pe", "op": ">", "value": 0}), (1.0, {"type": "pe", "op": "<=", "value": 30})])

    pattern_phrases = {
        "macd_golden_cross": r"MACD金叉|MACD翻红|DIF上穿DEA", "macd_dead_cross": r"MACD死叉|MACD翻绿|DIF下穿DEA",
        "macd_top_divergence": r"MACD?顶背离|顶背了", "macd_bottom_divergence": r"MACD?底背离|底背了",
        "kdj_golden_cross": r"KDJ金叉|K线上穿D|KD金叉", "kdj_dead_cross": r"KDJ死叉|K线下穿D|KD死叉",
        "boll_break_upper": r"突破布林上轨|布林上轨上方", "boll_break_lower": r"跌破布林下轨|布林下轨下方",
        "ma_bull_alignment": r"多头排列", "ma_bear_alignment": r"空头排列", "ma_convergence": r"均线粘合",
        "new_high_20d": r"20日新高|二十日新高", "big_yang": r"放量长阳", "low_volatility": r"低波动",
    }
    for name, pattern in pattern_phrases.items():
        if re.search(pattern, normalized, re.I):
            conditions.append((1.0, {"type": "factor", "name": name, "value": True}))

    alpha = re.search(r"(alpha191[_第]?(\d{1,2})|alpha[_]?(\d{1,3})).{0,8}?(>=|<=|>|<|大于|小于|以上|以下)(-?\d+(?:\.\d+)?)", normalized, re.I)
    if alpha:
        number = alpha.group(2) or alpha.group(3)
        name = f"alpha191_{int(number):02d}" if alpha.group(2) else f"alpha_{int(number):03d}"
        op = {"大于": ">", "小于": "<", "以上": ">=", "以下": "<="}.get(alpha.group(4), alpha.group(4))
        conditions.append((1.0, {"type": "factor", "name": name, "op": op, "value": float(alpha.group(5))}))
    generic = re.search(r"\b([a-z][a-z0-9_]+).{0,8}?(>=|<=|>|<|大于|小于|以上|以下)(-?\d+(?:\.\d+)?)", normalized, re.I)
    if generic and not generic.group(1).lower().startswith(("rps", "alpha")):
        name = generic.group(1).lower()
        auto_discover()
        if get_factor(name) is not None:
            op = {"大于": ">", "小于": "<", "以上": ">=", "以下": "<="}.get(generic.group(2), generic.group(2))
            conditions.append((1.0, {"type": "factor", "name": name, "op": op, "value": float(generic.group(3))}))

    industry = re.search(r"([\u4e00-\u9fff]{2,8})(?:行业|股)(?:里|中|的)?", normalized)
    if industry:
        value = industry.group(1)
        for prefix in ("选出", "选择", "我要", "找出", "再加", "筛选"):
            value = value.removeprefix(prefix)
        if value and not any(word in value for word in ("强势", "大盘", "小盘", "垃圾")):
            conditions.append((.8, {"type": "industry", "value": value}))

    unique: list[dict[str, Any]] = []
    seen = set()
    for _, condition in sorted(conditions, key=lambda item: item[0], reverse=True):
        marker = repr(sorted(condition.items()))
        if marker not in seen:
            seen.add(marker); unique.append(condition)
    return unique
