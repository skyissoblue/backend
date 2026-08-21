"""FastAPI service layer for the progressive selection engine."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    ConditionRequest,
    ConditionsResponse,
    PaginatedStocksResponse,
    ParseApplyResponse,
    ParseConditionRequest,
    SelectionResponse,
    SessionCreatedResponse,
    SessionResetResponse,
)
from .nlu_parser import parse_condition
from .session import SelectionSession
from .scheduler import start_scheduler, stop_scheduler


app = FastAPI(title="Progressive Stock Selection API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
session_store: dict[str, SelectionSession] = {}


@app.on_event("startup")
def startup() -> None:
    start_scheduler()


@app.on_event("shutdown")
def shutdown() -> None:
    stop_scheduler()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/factors")
def factors(kind: str | None = Query(default=None, pattern="^(ta|alpha|pattern)$")) -> dict[str, Any]:
    from factor_system.factor_lib.registry import auto_discover, list_all
    auto_discover()
    items = [item for item in list_all() if kind is None or item["kind"] == kind]
    return {"total": len(items), "factors": items}


def _get_session(session_id: str) -> SelectionSession:
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found",
        )
    return session


def _run_engine(operation, *args: Any) -> dict:
    try:
        return operation(*args)
    except (TypeError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@app.post("/api/session", response_model=SessionCreatedResponse)
def create_session() -> dict[str, Any]:
    session = SelectionSession()
    session_id = uuid4().hex
    session_store[session_id] = session
    return {"session_id": session_id, "total": len(session.stocks)}


@app.post(
    "/api/session/{session_id}/condition",
    response_model=SelectionResponse,
)
def apply_condition(
    session_id: str,
    condition: ConditionRequest,
) -> dict:
    session = _get_session(session_id)
    return _run_engine(session.apply_condition, condition.root)


@app.delete(
    "/api/session/{session_id}/condition/last",
    response_model=SelectionResponse,
)
def remove_last_condition(session_id: str) -> dict:
    return _get_session(session_id).remove_last()


@app.delete(
    "/api/session/{session_id}",
    response_model=SessionResetResponse,
)
def reset_session(session_id: str) -> dict[str, Any]:
    session = _get_session(session_id)
    result = session.reset()
    return {"session_id": session_id, "total": result["after"]}


@app.get(
    "/api/session/{session_id}/stocks",
    response_model=PaginatedStocksResponse,
)
def get_stocks(
    session_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=500),
) -> dict[str, Any]:
    stocks = _get_session(session_id).stocks
    start = (page - 1) * size
    return {
        "page": page,
        "size": size,
        "total": len(stocks),
        "stocks": stocks[start : start + size],
    }


@app.get(
    "/api/session/{session_id}/conditions",
    response_model=ConditionsResponse,
)
def get_conditions(session_id: str) -> list[dict[str, Any]]:
    return _get_session(session_id).conditions


@app.post(
    "/api/session/{session_id}/parse-and-apply",
    response_model=ParseApplyResponse,
)
def parse_and_apply(
    session_id: str,
    request: ParseConditionRequest,
) -> dict[str, Any]:
    session = _get_session(session_id)
    parsed = parse_condition(request.text, session.conditions)
    action = parsed.get("action")

    if action == "error":
        return parsed
    if action == "add":
        condition = parsed.get("condition")
        if not isinstance(condition, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="add action requires a condition",
            )
        result = _run_engine(session.apply_condition, condition)
    elif action == "remove_last":
        result = session.remove_last()
    elif action == "reset":
        result = session.reset()
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="unsupported parser action",
        )

    return {**parsed, **result}
