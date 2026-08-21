"""Backward-compatible exports for the DeepSeek NLU package."""

from .nlu.parser import NLUResult as ParsedCondition
from .nlu.parser import parse as parse_condition
from .nlu.parser import parse_batch

__all__ = ["ParsedCondition", "parse_condition", "parse_batch"]
