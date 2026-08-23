from fastapi.testclient import TestClient
from selection_engine import api, database, voice

def test_voice_requires_auth():
    with TestClient(api.app) as client:
        assert client.post("/api/voice/transcribe", files={"audio": ("a.wav", b"RIFF")}).status_code == 401

def test_voice_transcription(monkeypatch):
    monkeypatch.setattr(database, "get_user_by_id", lambda user_id: {"id": user_id, "phone": "13800138000", "nickname": None})
    monkeypatch.setattr(voice, "transcribe", lambda path: "站上十周线")
    from selection_engine.auth.jwt_handler import create_token
    with TestClient(api.app) as client:
        response = client.post("/api/voice/transcribe", headers={"Authorization": f"Bearer {create_token(1)}"}, files={"audio": ("a.wav", b"RIFF")})
        assert response.status_code == 200
        assert response.json() == {"text": "站上十周线"}
