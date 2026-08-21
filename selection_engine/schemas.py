"""Pydantic request and response models for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, RootModel


class ConditionRequest(RootModel[dict[str, Any]]):
    pass


class ParseConditionRequest(BaseModel):
    text: str = Field(min_length=1)


class StockResponse(BaseModel):
    code: str
    name: str


class SessionCreatedResponse(BaseModel):
    session_id: str
    total: int


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
    message: str | None = None
    before: int | None = None
    after: int | None = None
    removed: int | None = None
    stocks: list[StockResponse] | None = None
