"""DeepSeek NLU, composite aliases, validation and context tests."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from selection_engine.nlu import aliases, parser
from selection_engine.nlu.context import NLUContext


class FakeCompletions:
    def __init__(self, payload): self.payload, self.request = payload, None
    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.payload)))])


class FakeClient:
    def __init__(self, payload): self.chat = SimpleNamespace(completions=FakeCompletions(payload))


@pytest.mark.parametrize("text,board", [
    ("创业板", "创业板"), ("3开头的", "创业板"), ("300开头", "创业板"),
    ("科创板的", "科创板"), ("688开头", "科创板"), ("主板", "主板"),
    ("60开头", "主板"), ("00开头", "主板"), ("北交所", "北交所"), ("8开头", "北交所"),
])
def test_board_aliases(text, board):
    assert aliases.match_alias(text)[0] == {"type": "board", "value": board}


@pytest.mark.parametrize("text,expected", [
    ("站上10周线", {"type": "ma_cross_weekly"}),
    ("站上20日线", {"type": "ma_cross", "period": "daily", "ma": 20, "op": ">="}),
    ("跌破20日线", {"type": "ma_cross", "period": "daily", "ma": 20, "op": "<"}),
    ("5日线上穿10日线", {"type": "ma_cross", "period": "daily", "ma_fast": 5, "ma_slow": 10, "cross": "golden"}),
    ("站上5月线", {"type": "ma_cross", "period": "monthly", "ma": 5, "op": ">="}),
    ("跌破10年线", {"type": "ma_cross", "period": "yearly", "ma": 10, "op": "<"}),
    ("5周线金叉10周线", {"type": "ma_cross", "period": "weekly", "ma_fast": 5, "ma_slow": 10, "cross": "golden"}),
    ("5月线死叉10月线", {"type": "ma_cross", "period": "monthly", "ma_fast": 5, "ma_slow": 10, "cross": "death"}),
])
def test_ma_aliases(text, expected):
    assert parser.parse(text)["condition"] == expected


def test_ma_deviation_supports_monthly_and_yearly_periods():
    assert parser.parse("偏离10月线不超过8%")['condition'] == {
        "type": "ma_deviation", "period": "monthly", "ma": 10, "max_pct": 8.0,
    }
    assert parser.parse("偏离5年线不超过12%")['condition']["period"] == "yearly"


@pytest.mark.parametrize("text,op", [
    ("年线上方", ">="),
    ("站上年线", ">="),
    ("股价高于年线", ">="),
    ("年线下方", "<"),
    ("跌破年线", "<"),
])
def test_unqualified_annual_line_means_250_day_ma(text, op):
    assert parser.parse(text)["condition"] == {
        "type": "ma_cross",
        "period": "daily",
        "ma": 250,
        "op": op,
    }


def test_fuzzy_strength_and_composite():
    assert parser.parse("最近比较强势的")["condition"] == {"type": "rps", "op": ">=", "value": 80}
    result = parser.parse("科技股里站上10周线并且RPS大于87")
    assert {item["type"] for item in result["conditions"]} == {"industry", "ma_cross_weekly", "rps"}
    assert len(parser.parse("低位启动")["conditions"]) == 2
    assert parser.parse("RPS排名前5%")["condition"] == {"type": "rps", "op": ">=", "value": 95}
    valuation = parser.parse("估值合理的公司")["conditions"]
    assert valuation == [{"type": "pe", "op": ">", "value": 0}, {"type": "pe", "op": "<=", "value": 30}]


def test_deepseek_composite_and_context(monkeypatch):
    payload = {"action": "add", "conditions": [
        {"type": "board_match", "value": "创业板"},
        {"type": "pattern", "name": "ma_bull_alignment", "value": True},
    ]}
    fake = FakeClient(payload)
    monkeypatch.setattr(parser, "match_alias", lambda text: [])
    monkeypatch.setattr(parser, "DeepSeekClient", lambda **kwargs: fake)
    result = parser.parse("寻找成长板中趋势结构健康的股票", [{"type": "rps", "op": ">", "value": 80}])
    assert result["source"] == "deepseek"
    assert result["conditions"][0] == {"type": "board", "value": "创业板"}
    assert result["conditions"][1]["type"] == "factor"
    assert "当前已有条件" in fake.chat.completions.request["messages"][0]["content"]


def test_invalid_factor_is_rejected(monkeypatch):
    fake = FakeClient({"action": "add", "conditions": [{"type": "alpha", "name": "invented_alpha", "op": ">", "value": 1}]})
    monkeypatch.setattr(parser, "match_alias", lambda text: [])
    monkeypatch.setattr(parser, "DeepSeekClient", lambda **kwargs: fake)
    assert parser.parse("复杂且未知的量价逻辑")["action"] == "error"


def test_alias_fallback_on_deepseek_failure(monkeypatch):
    calls = iter([[], [{"type": "rps", "op": ">=", "value": 80}]])
    monkeypatch.setattr(parser, "match_alias", lambda text: next(calls))
    monkeypatch.setattr(parser, "DeepSeekClient", lambda **kwargs: (_ for _ in ()).throw(ConnectionError("offline")))
    result = parser.parse("强势")
    assert result["source"] == "alias_fallback"


def test_control_and_invalid_input():
    assert parser.parse("撤销上一步")["action"] == "remove_last"
    assert parser.parse("重新来")["action"] == "reset"
    assert parser.parse("")["action"] == "error"


def test_mmc_rsi_uses_local_builtin_formula(monkeypatch):
    monkeypatch.setattr(
        parser,
        "_deepseek",
        lambda *_: (_ for _ in ()).throw(AssertionError("DeepSeek must not be called")),
    )
    result = parser.parse("帮我运行 mmc_rsi")
    assert result["source"] == "alias"
    assert result["condition"] == {
        "type": "factor",
        "name": "mmc_rsi",
        "value": True,
    }


def test_context_format():
    text = NLUContext([{"type": "board", "value": "创业板"}]).to_prompt()
    assert "当前已有条件" in text and "创业板" in text
