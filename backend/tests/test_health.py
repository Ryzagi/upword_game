from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_ok() -> None:
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "version" in body
