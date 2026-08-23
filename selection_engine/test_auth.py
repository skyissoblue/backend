from fastapi.testclient import TestClient
from selection_engine import api, database


def test_register_login_and_me(monkeypatch):
    users = {}

    def by_phone(phone):
        return users.get(phone)

    def create(phone, nickname, password_hash):
        user = {"id": 1, "phone": phone, "nickname": nickname, "password_hash": password_hash}
        users[phone] = user
        return user

    monkeypatch.setattr(database, "get_user_by_phone", by_phone)
    monkeypatch.setattr(database, "create_user", create)
    monkeypatch.setattr(database, "get_user_by_id", lambda user_id: users.get("13800138000") if user_id == 1 else None)
    with TestClient(api.app) as client:
        registered = client.post("/api/auth/register", json={"phone": "13800138000", "password": "password123", "nickname": "测试用户"})
        assert registered.status_code == 201
        token = registered.json()["token"]
        assert client.post("/api/auth/login", json={"phone": "13800138000", "password": "wrong-pass"}).status_code == 401
        logged_in = client.post("/api/auth/login", json={"phone": "13800138000", "password": "password123"})
        assert logged_in.status_code == 200
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["phone"] == "13800138000"


def test_me_requires_token():
    with TestClient(api.app) as client:
        assert client.get("/api/auth/me").status_code == 401
