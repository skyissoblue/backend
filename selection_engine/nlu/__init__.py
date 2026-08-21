"""DeepSeek-backed natural-language understanding for stock selection."""

from .parser import NLUResult, parse, parse_batch

__all__ = ["NLUResult", "parse", "parse_batch"]
