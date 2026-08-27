"""Pydantic request and response models for the HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel


class ConditionRequest(RootModel[dict[str, Any]]):
    pass


class ParseConditionRequest(BaseModel):
    text: str = Field(min_length=1)


class CreateSessionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    asset_type: Literal["stock", "etf"] = "stock"


class RenameSessionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class RegisterRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    password: str = Field(min_length=8, max_length=72)
    nickname: str | None = Field(default=None, max_length=50)


class LoginRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    password: str = Field(min_length=8, max_length=72)


class AuthResponse(BaseModel):
    token: str
    user_id: int
    phone: str
    nickname: str | None = None


class UserResponse(BaseModel):
    user_id: int
    phone: str
    nickname: str | None = None


class ComboCreateRequest(BaseModel):
    name: str = Field(default="默认组合", min_length=1, max_length=100)
    asset_type: Literal["stock", "etf"] = "stock"


class ComboPatchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class FavoriteRequest(BaseModel):
    favorite: bool


class WatchlistCreateRequest(BaseModel):
    stock_code: str = Field(min_length=6, max_length=10)
    stock_name: str | None = Field(default=None, max_length=64)
    source_combo_id: int | None = None


class StockResponse(BaseModel):
    code: str
    name: str


class SessionCreatedResponse(BaseModel):
    session_id: str
    name: str
    total: int


class SessionSummaryResponse(BaseModel):
    session_id: str
    name: str
    current_count: int
    condition_count: int


class SessionDetailResponse(BaseModel):
    session_id: str
    name: str
    conditions: list[dict[str, Any]]
    total: int
    current_count: int
    stocks: list[StockResponse]


class RenameSessionResponse(BaseModel):
    session_id: str
    name: str


class DropSessionResponse(BaseModel):
    dropped: bool


class SelectionResponse(BaseModel):
    before: int
    after: int
    removed: int
    stocks: list[StockResponse]


class SessionResetResponse(BaseModel):
    session_id: str
    total: int


class PaginatedStocksResponse(BaseModel):
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    total: int = Field(ge=0)
    stocks: list[StockResponse]


class ConditionsResponse(RootModel[list[dict[str, Any]]]):
    pass


class ParseApplyResponse(BaseModel):
    action: str
    condition: dict[str, Any] | None = None
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    applied_conditions: list[dict[str, Any]] = Field(default_factory=list)
    source: str | None = None
    message: str | None = None
    before: int | None = None
    after: int | None = None
    removed: int | None = None
    stocks: list[StockResponse] | None = None
