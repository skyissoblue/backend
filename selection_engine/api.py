"""FastAPI service layer for the progressive selection engine."""

from __future__ import annotations

from typing import Any
from uuid import uuid4
import json

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    ConditionRequest,
    AuthResponse,
    ConditionsResponse,
    CreateSessionRequest,
    DropSessionResponse,
    PaginatedStocksResponse,
    ParseApplyResponse,
    ParseConditionRequest,
    LoginRequest,
    RegisterRequest,
    RenameSessionRequest,
    RenameSessionResponse,
    SelectionResponse,
    SessionCreatedResponse,
    SessionDetailResponse,
    SessionResetResponse,
    SessionSummaryResponse,
    UserResponse,
    ComboCreateRequest,
    ComboPatchRequest,
    FavoriteRequest,
    WatchlistCreateRequest,
)
from . import database
from .auth.deps import get_current_user
from .auth.jwt_handler import create_token
from .auth.password import hash_password, verify_password
from .nlu import parse as parse_condition
from .session import SelectionSession
from .scheduler import start_scheduler, stop_scheduler
from . import local_store


app = FastAPI(title="Progressive Stock Selection API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
session_store: dict[str, SelectionSession] = {}
session_names: dict[str, str] = {}


@app.on_event("startup")
def startup() -> None:
    start_scheduler()


@app.on_event("shutdown")
def shutdown() -> None:
    stop_scheduler()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest) -> dict[str, Any]:
    try:
        if database.get_user_by_phone(request.phone) is not None:
            raise HTTPException(status_code=409, detail="phone already registered")
        user = database.create_user(request.phone, request.nickname, hash_password(request.password))
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="user database unavailable") from error
    return {"token": create_token(user["id"]), "user_id": user["id"], "phone": user["phone"], "nickname": user.get("nickname")}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: LoginRequest) -> dict[str, Any]:
    try:
        user = database.get_user_by_phone(request.phone)
    except Exception as error:
        raise HTTPException(status_code=503, detail="user database unavailable") from error
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid phone or password")
    return {"token": create_token(user["id"]), "user_id": user["id"], "phone": user["phone"], "nickname": user.get("nickname")}


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return {"user_id": user["id"], "phone": user["phone"], "nickname": user.get("nickname")}


def _json(value: Any) -> list:
    if isinstance(value, str): return json.loads(value)
    return value or []


def _combo_session(user_id: int, combo_id: int) -> tuple[dict[str, Any], SelectionSession]:
    combo = database.get_combo(user_id, combo_id)
    if combo is None: raise HTTPException(status_code=404, detail="combo not found")
    key = f"combo:{user_id}:{combo_id}"
    session = session_store.get(key)
    if session is None:
        session = SelectionSession()
        for condition in _json(combo["conditions_json"]): _run_engine(session.apply_condition, condition)
        session_store[key] = session
    return combo, session


def _save_combo(user_id: int, combo_id: int, session: SelectionSession) -> None:
    database.update_combo(user_id, combo_id, conditions_json=json.dumps(session.conditions, ensure_ascii=False), result_codes=json.dumps([item["code"] for item in session.stocks]), result_count=len(session.stocks))


@app.post("/api/combos", status_code=201)
def create_combo(request: ComboCreateRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    session = SelectionSession(); combo_id = database.create_combo(user["id"], request.name.strip(), session.total)
    session_store[f"combo:{user['id']}:{combo_id}"] = session
    return {"combo_id": combo_id, "name": request.name.strip(), "total": session.total, "current_count": session.total}


@app.get("/api/combos")
def combos(favorite: bool | None = None, user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    return [{"combo_id": row["id"], "name": row["name"], "current_count": row["result_count"], "condition_count": len(_json(row["conditions_json"])), "is_favorite": bool(row["is_favorite"])} for row in database.list_combos(user["id"], favorite)]


@app.get("/api/combos/{combo_id}")
def combo_detail(combo_id: int, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    combo, session = _combo_session(user["id"], combo_id)
    return {"combo_id": combo_id, "name": combo["name"], "conditions": session.conditions, "total": session.total, "current_count": len(session.stocks), "is_favorite": bool(combo["is_favorite"]), "stocks": session.stocks[:100]}


@app.patch("/api/combos/{combo_id}")
def patch_combo(combo_id: int, request: ComboPatchRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    _combo_session(user["id"], combo_id); database.update_combo(user["id"], combo_id, name=request.name.strip()); return {"ok": True}


@app.delete("/api/combos/{combo_id}")
def remove_combo(combo_id: int, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    _combo_session(user["id"], combo_id); database.delete_combo(user["id"], combo_id); session_store.pop(f"combo:{user['id']}:{combo_id}", None); return {"ok": True}


@app.post("/api/combos/{combo_id}/favorite")
def favorite_combo(combo_id: int, request: FavoriteRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    _combo_session(user["id"], combo_id); database.update_combo(user["id"], combo_id, is_favorite=int(request.favorite)); return {"favorite": request.favorite}


@app.post("/api/combos/{combo_id}/condition")
def combo_condition(combo_id: int, condition: ConditionRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    _, session = _combo_session(user["id"], combo_id); result = _run_engine(session.apply_condition, condition.root); _save_combo(user["id"], combo_id, session); return result


@app.delete("/api/combos/{combo_id}/condition/{index}")
def combo_remove_condition(combo_id: int, index: int, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    _, session = _combo_session(user["id"], combo_id); result = _run_engine(session.remove_at, index); _save_combo(user["id"], combo_id, session); return {**result, "conditions": session.conditions}


@app.post("/api/combos/{combo_id}/parse")
def combo_parse(combo_id: int, request: ParseConditionRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    _, session = _combo_session(user["id"], combo_id); result = _parse_and_apply(session, request.text); _save_combo(user["id"], combo_id, session); return result


@app.post("/api/combos/{combo_id}/reset")
def combo_reset(combo_id: int, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    _, session = _combo_session(user["id"], combo_id); result = session.reset(); _save_combo(user["id"], combo_id, session); return result


@app.post("/api/watchlist", status_code=201)
def add_watchlist(request: WatchlistCreateRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    combo_name = None
    if request.source_combo_id is not None:
        combo = database.get_combo(user["id"], request.source_combo_id)
        if combo is None: raise HTTPException(status_code=404, detail="source combo not found")
        combo_name = combo["name"]
    database.upsert_watchlist(user["id"], request.stock_code, request.stock_name, request.source_combo_id, combo_name); return {"ok": True}


@app.get("/api/watchlist/by-combo")
def grouped_watchlist(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in database.list_watchlist(user["id"]):
        key = str(row.get("source_combo_id") or "other")
        group = groups.setdefault(key, {"combo_id": row.get("source_combo_id"), "combo_name": row.get("source_combo_name") or "其他", "stocks": []})
        group["stocks"].append({"code": row["stock_code"], "name": row.get("stock_name"), "note": row.get("note")})
    return list(groups.values())


@app.delete("/api/watchlist/{stock_code}")
def remove_watchlist(stock_code: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    database.delete_watchlist(user["id"], stock_code); return {"ok": True}


@app.get("/api/factors")
def factors(kind: str | None = Query(default=None, pattern="^(ta|alpha|pattern)$")) -> dict[str, Any]:
    from factor_system.factor_lib.registry import auto_discover, list_all
    auto_discover()
    items = [item for item in list_all() if kind is None or item["kind"] == kind]
    return {"total": len(items), "factors": items}


@app.get("/api/stock/{code}/kline")
def stock_kline(code: str, period: str = Query(default="daily", pattern="^(daily|weekly|monthly|yearly)$"), user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    frame = local_store.load(code)
    if frame.empty: raise HTTPException(status_code=404, detail="kline not found")
    if period != "daily":
        rules = {"weekly": "W-FRI", "monthly": "ME", "yearly": "YE"}
        frame = frame.set_index("date").resample(rules[period]).agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum","amount":"sum"}).dropna(subset=["open","close"]).reset_index()
    return [{"date": row.date.date().isoformat(), "open": float(row.open), "high": float(row.high), "low": float(row.low), "close": float(row.close), "volume": float(row.volume), "amount": float(row.amount)} for row in frame.itertuples()]


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
    except (TypeError, ValueError, KeyError, IndexError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@app.post("/api/session", response_model=SessionCreatedResponse)
def create_session(request: CreateSessionRequest | None = None) -> dict[str, Any]:
    session = SelectionSession()
    session_id = uuid4().hex
    session_store[session_id] = session
    name = request.name.strip() if request and request.name else f"组合{len(session_store)}"
    session_names[session_id] = name
    return {"session_id": session_id, "name": name, "total": len(session.stocks)}


@app.get("/api/session", response_model=list[SessionSummaryResponse])
def list_sessions() -> list[dict[str, Any]]:
    return [
        {
            "session_id": session_id,
            "name": session_names.get(session_id, "未命名组合"),
            "current_count": len(session.stocks),
            "condition_count": len(session.conditions),
        }
        for session_id, session in session_store.items()
    ]


@app.get("/api/session/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(session_id: str) -> dict[str, Any]:
    session = _get_session(session_id)
    return {
        "session_id": session_id,
        "name": session_names.get(session_id, "未命名组合"),
        "conditions": session.conditions,
        "total": session.total,
        "current_count": len(session.stocks),
        "stocks": session.stocks,
    }


@app.post("/api/session/{session_id}/rename", response_model=RenameSessionResponse)
def rename_session(session_id: str, request: RenameSessionRequest) -> dict[str, str]:
    _get_session(session_id)
    session_names[session_id] = request.name.strip()
    return {"session_id": session_id, "name": session_names[session_id]}


@app.delete("/api/session/{session_id}/drop", response_model=DropSessionResponse)
def drop_session(session_id: str) -> dict[str, bool]:
    _get_session(session_id)
    del session_store[session_id]
    session_names.pop(session_id, None)
    return {"dropped": True}


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
    "/api/session/{session_id}/condition/{index}",
    response_model=SelectionResponse,
)
def remove_condition(session_id: str, index: int) -> dict:
    return _run_engine(_get_session(session_id).remove_at, index)


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
    return _parse_and_apply(_get_session(session_id), request.text)


@app.post("/api/session/{session_id}/parse", response_model=ParseApplyResponse)
def parse_natural_language(session_id: str, request: ParseConditionRequest) -> dict[str, Any]:
    return _parse_and_apply(_get_session(session_id), request.text)


def _parse_and_apply(session: SelectionSession, text: str) -> dict[str, Any]:
    parsed = parse_condition(text, session.conditions)
    action = parsed.get("action")

    if action == "error":
        return parsed
    if action == "add":
        conditions = parsed.get("conditions") or ([parsed["condition"]] if isinstance(parsed.get("condition"), dict) else [])
        if not conditions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="add action requires conditions",
            )
        before = len(session.stocks)
        for condition in conditions:
            _run_engine(session.apply_condition, condition)
        result = {"before": before, "after": len(session.stocks), "removed": max(before - len(session.stocks), 0), "stocks": session.stocks}
    elif action == "remove_last":
        result = session.remove_last()
    elif action == "reset":
        result = session.reset()
    elif action == "remove_specific":
        before = len(session.stocks)
        for condition in parsed.get("conditions", []):
            session.remove_specific(condition)
        result = {"before": before, "after": len(session.stocks), "removed": max(before - len(session.stocks), 0), "stocks": session.stocks}
    elif action == "replace":
        conditions = parsed.get("conditions", [])
        before = len(session.stocks)
        for condition in conditions: session.remove_specific(condition)
        for condition in conditions: _run_engine(session.apply_condition, condition)
        result = {"before": before, "after": len(session.stocks), "removed": max(before - len(session.stocks), 0), "stocks": session.stocks}
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="unsupported parser action",
        )

    return {**parsed, **result, "applied_conditions": session.conditions}
