"""Formatting and mutation helpers for NLU session context."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


def format_condition(condition: dict[str, Any]) -> str:
    return json.dumps(condition, ensure_ascii=False, separators=(",", ":"))


class NLUContext:
    def __init__(self, session_conditions: list[dict[str, Any]] | None = None) -> None:
        self.conditions = deepcopy(session_conditions or [])

    def add(self, condition: dict[str, Any]) -> None:
        self.conditions.append(deepcopy(condition))

    def remove_last(self) -> None:
        if self.conditions:
            self.conditions.pop()

    def to_prompt(self) -> str:
        if not self.conditions:
            return "当前无筛选条件。"
        lines = ["当前已有条件："]
        lines.extend(f"{index}. {format_condition(condition)}" for index, condition in enumerate(self.conditions, 1))
        return "\n".join(lines)
