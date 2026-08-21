"""Plugin-based local factor calculation system."""

from .factor_lib.registry import auto_discover, get, list_all, list_by_kind

__all__ = ["auto_discover", "get", "list_all", "list_by_kind"]
