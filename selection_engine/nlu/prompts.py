"""DeepSeek system prompt and executable condition taxonomy."""
from __future__ import annotations

from factor_system.factor_lib.registry import auto_discover, list_by_kind

from .context import NLUContext

CONDITION_TYPES = {
    "board_match": "板块匹配：创业板、科创板、主板、北交所",
    "exclude_st": "排除 ST、*ST 股票",
    "industry": "行业或概念关键词",
    "ma_cross": "价格站上/跌破均线，或两条均线交叉",
    "ma_deviation": "价格偏离均线百分比",
    "rps": "RPS 强度排名",
    "volume_ratio": "量比、放量、缩量",
    "market_cap": "总市值（单位元）",
    "pe": "市盈率",
    "macd_cross": "MACD 金叉或死叉",
    "macd_divergence": "MACD 顶背离或底背离",
    "rsi": "RSI 数值条件",
    "boll": "布林带突破",
    "kdj_cross": "KDJ 金叉或死叉",
    "alpha": "已注册 Alpha 因子",
    "pattern": "已注册形态因子",
    "factor": "其他已注册技术因子",
}


def build_system_prompt(context: list[dict] | None = None) -> str:
    auto_discover()
    alpha_names = ",".join(list_by_kind("alpha"))
    pattern_names = ",".join(list_by_kind("pattern"))
    types = "\n".join(f"- {name}: {description}" for name, description in CONDITION_TYPES.items())
    return f"""你是A股选股条件解析器。将用户任意自然语言转换成程序可执行的合法 JSON 对象；只输出 JSON，不要解释、Markdown或代码块。

输出格式：
{{"action":"add|remove_last|reset|remove_specific|replace","conditions":[{{"type":"条件类型"}}],"message":null}}
一句话包含多个条件时，conditions 必须逐项列出。比较运算仅允许 >、>=、<、<=、==、!=。

条件类型：
{types}

映射规则：
- 3/300/301开头、创业板票→board_match创业板；688/科创→科创板；60或00开头→主板；8或4开头、北交→北交所。
- 不要ST、排除ST、非ST→exclude_st=true。
- 站上10周线→ma_cross(period=weekly,ma=10,op=>=)；跌破20日线→ma_cross(period=daily,ma=20,op=<)。
- 5日线上穿10日线→ma_cross(period=daily,ma_fast=5,ma_slow=10,cross=golden)。
- 偏离10周线不超过10%→ma_deviation(period=weekly,ma=10,max_pct=10)。
- RPS前5%→rps>=95；强势/涨得好→rps>=80；低位/超跌→rps<=20。
- 放量→volume_ratio>=2；缩量→volume_ratio<=0.8；热门活跃→volume_ratio>=1.5。
- 低位放量启动必须拆成 rps<=30 和 volume_ratio>=2 两项。
- 大盘权重→market_cap>=50000000000；小盘迷你盘→market_cap<=5000000000。
- MACD金叉/死叉→macd_cross golden/death；顶背离/底背离→macd_divergence top/bottom。
- RSI超买→rsi>=70；RSI超卖→rsi<=30；布林上下轨、KDJ金死叉按对应类型输出。
- alpha/pattern/factor 的 name 只能从下方注册表选择，禁止编造不存在的因子。
- “再加、并且、而且”表示add；“撤销上一步”表示remove_last；“重置、从头”表示reset；“换成、改成”表示replace。

可用 Alpha：{alpha_names}
可用形态：{pattern_names}

{NLUContext(context).to_prompt()}
"""
