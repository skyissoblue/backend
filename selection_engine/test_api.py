"""HTTP API tests; all market-data access is mocked."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from selection_engine import api, data_provider


def _stocks() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code": ["000001", "300001", "688001", "800001"],
            "name": ["科技一", "医药二", "科技三", "消费四"],
        }
    )


def _stock_info(code: str) -> dict:
    return {
        "code": code,
        "name": f"股票{code}",
        "industry": "科技" if code in {"000001", "688001"} else "其他",
        "board": "创业板" if code.startswith("300") else "主板",
        "market_cap": 10_000_000_000,
        "pe": 20.0,
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(data_provider, "get_all_stocks", _stocks)
    monkeypatch.setattr(data_provider, "get_stock_info", _stock_info)
    api.session_store.clear()
    with TestClient(api.app) as test_client:
        yield test_client
    api.session_store.clear()


def _create_session(client: TestClient) -> str:
    response = client.post("/api/session")
    assert response.status_code == 200
    assert response.json()["total"] == 4
    return response.json()["session_id"]


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_session(client):
    session_id = _create_session(client)
    assert session_id in api.session_store


def test_apply_condition_and_list_conditions(client):
    session_id = _create_session(client)
    condition = {"type": "industry", "value": "科技"}
    response = client.post(
        f"/api/session/{session_id}/condition",
        json=condition,
    )
    assert response.status_code == 200
    assert response.json()["before"] == 4
    assert response.json()["after"] == 2
    assert response.json()["removed"] == 2

    response = client.get(f"/api/session/{session_id}/conditions")
    assert response.status_code == 200
    assert response.json() == [condition]


def test_paginated_stocks(client):
    session_id = _create_session(client)
    response = client.get(
        f"/api/session/{session_id}/stocks",
        params={"page": 2, "size": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["size"] == 2
    assert body["total"] == 4
    assert [stock["code"] for stock in body["stocks"]] == ["688001", "800001"]


def test_remove_last_condition(client):
    session_id = _create_session(client)
    client.post(
        f"/api/session/{session_id}/condition",
        json={"type": "industry", "value": "科技"},
    )
    response = client.delete(
        f"/api/session/{session_id}/condition/last"
    )
    assert response.status_code == 200
    assert response.json()["after"] == 4
    assert len(response.json()["stocks"]) == 4


def test_reset_session(client):
    session_id = _create_session(client)
    client.post(
        f"/api/session/{session_id}/condition",
        json={"type": "industry", "value": "科技"},
    )
    response = client.delete(f"/api/session/{session_id}")
    assert response.status_code == 200
    assert response.json() == {"session_id": session_id, "total": 4}
    assert api.session_store[session_id].conditions == []


def test_missing_session_returns_404(client):
    response = client.get("/api/session/missing/stocks")
    assert response.status_code == 404


def test_invalid_condition_returns_422(client):
    session_id = _create_session(client)
    response = client.post(
        f"/api/session/{session_id}/condition",
        json={"type": "unknown"},
    )
    assert response.status_code == 422


def test_parse_and_apply(client, monkeypatch):
    session_id = _create_session(client)
    monkeypatch.setattr(
        api,
        "parse_condition",
        lambda text, context: {
            "action": "add",
            "condition": {"type": "industry", "value": "科技"},
        },
    )
    response = client.post(
        f"/api/session/{session_id}/parse-and-apply",
        json={"text": "科技股"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "add"
    assert body["before"] == 4
    assert body["after"] == 2
