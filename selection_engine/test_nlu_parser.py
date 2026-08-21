"""Tests for OpenAI-backed natural-language condition parsing."""

from types import SimpleNamespace

import pytest

from selection_engine import nlu_parser
from selection_engine.nlu_parser import ParsedCondition


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None

    def parse(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(
            output_parsed=ParsedCondition.model_validate(self.payload)
        )


class FakeClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


@pytest.mark.parametrize(
    ("text", "payload", "expected"),
    [
        (
            "科技股",
            {"action": "add", "condition": {"type": "industry", "value": "科技"}},
            {"type": "industry", "value": "科技"},
        ),
        (
            "站上10周线",
            {"action": "add", "condition": {"type": "ma_cross_weekly"}},
            {"type": "ma_cross_weekly"},
        ),
        (
            "RPS大于87",
            {"action": "add", "condition": {"type": "rps", "op": ">", "value": 87}},
            {"type": "rps", "op": ">", "value": 87},
        ),
    ],
)
def test_parse_common_conditions(monkeypatch, text, payload, expected):
    fake = FakeClient(payload)
    monkeypatch.setattr(nlu_parser, "OpenAI", lambda: fake)
    result = nlu_parser.parse_condition(text)
    assert result["action"] == "add"
    assert result["condition"] == expected


def test_incremental_parse_includes_context(monkeypatch):
    payload = {"action": "add", "condition": {"type": "volume_ratio", "op": ">", "value": 1.5}}
    fake = FakeClient(payload)
    monkeypatch.setattr(nlu_parser, "OpenAI", lambda: fake)
    context = [{"type": "industry", "value": "科技"}]
    result = nlu_parser.parse_condition("结合已有条件继续筛选强势标的", context)
    assert result["condition"]["type"] == "volume_ratio"
    system_prompt = fake.responses.last_request["input"][0]["content"]
    assert '"type": "industry"' in system_prompt
    assert '"value": "科技"' in system_prompt


def test_api_failure_returns_error(monkeypatch):
    def fail():
        raise RuntimeError("service unavailable")
    monkeypatch.setattr(nlu_parser, "OpenAI", fail)
    result = nlu_parser.parse_condition("无法识别的复杂条件")
    assert result == {"action": "error", "message": "service unavailable"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("科技股", {"action": "add", "condition": {"type": "industry", "value": "科技"}}),
        ("站上10周线", {"action": "add", "condition": {"type": "ma_cross_weekly"}}),
        ("RPS大于87", {"action": "add", "condition": {"type": "rps", "op": ">", "value": 87}}),
        ("再加个成交量放大的", {"action": "add", "condition": {"type": "volume_ratio", "op": ">", "value": 1.5}}),
        ("撤销上一步", {"action": "remove_last"}),
    ],
)
def test_local_fallback_when_openai_unavailable(monkeypatch, text, expected):
    monkeypatch.setattr(nlu_parser, "OpenAI", lambda: (_ for _ in ()).throw(ConnectionError("offline")))
    assert nlu_parser.parse_condition(text) == expected
