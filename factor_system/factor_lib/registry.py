"""Central factor plugin registry."""
from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import Any

FACTOR_REGISTRY: dict[str, dict[str, Any]] = {}


def register(name: str, kind: str, func: Callable, fields: list[str] | None = None, desc: str = "") -> None:
    if name in FACTOR_REGISTRY:
        raise ValueError(f"factor already registered: {name}")
    if kind not in {"ta", "alpha", "pattern"}:
        raise ValueError(f"unsupported factor kind: {kind}")
    FACTOR_REGISTRY[name] = {"name": name, "kind": kind, "func": func, "fields": fields or [name], "desc": desc}


def get(name: str) -> dict[str, Any] | None:
    return FACTOR_REGISTRY.get(name)


def list_all() -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key != "func"} for _, item in sorted(FACTOR_REGISTRY.items())]


def list_by_kind(kind: str) -> list[str]:
    return sorted(name for name, item in FACTOR_REGISTRY.items() if item["kind"] == kind)


def unregister(name: str) -> None:
    FACTOR_REGISTRY.pop(name, None)


def auto_discover() -> None:
    package = importlib.import_module(__package__)
    for module in pkgutil.iter_modules(package.__path__):
        if module.name not in {"registry", "composite"}:
            importlib.import_module(f"{__package__}.{module.name}")
