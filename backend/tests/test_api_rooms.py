from fastapi.testclient import TestClient

from app.main import app


def test_create_room_returns_code_and_credentials() -> None:
    with TestClient(app) as client:
        r = client.post("/api/rooms", json={"nickname": "Alex"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "code" in body
        assert len(body["code"]) == 6
        assert "player_id" in body
        assert "token" in body


def test_create_room_rejects_empty_nickname() -> None:
    with TestClient(app) as client:
        r = client.post("/api/rooms", json={"nickname": "   "})
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "nickname_invalid"


def test_join_room_returns_credentials_for_existing_room() -> None:
    with TestClient(app) as client:
        r = client.post("/api/rooms", json={"nickname": "Alex"})
        code = r.json()["code"]
        r2 = client.post(f"/api/rooms/{code}/join", json={"nickname": "Mira"})
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["code"] == code
        assert "player_id" in body
        assert "token" in body


def test_join_room_rejects_duplicate_nickname() -> None:
    with TestClient(app) as client:
        r = client.post("/api/rooms", json={"nickname": "Alex"})
        code = r.json()["code"]
        r2 = client.post(f"/api/rooms/{code}/join", json={"nickname": "alex"})
        assert r2.status_code == 409
        assert r2.json()["detail"]["error"]["code"] == "nickname_taken"


def test_join_unknown_room_returns_404() -> None:
    with TestClient(app) as client:
        r = client.post("/api/rooms/ZZZZZZ/join", json={"nickname": "Mira"})
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "room_not_found"


def test_get_room_returns_public_snapshot() -> None:
    with TestClient(app) as client:
        r = client.post("/api/rooms", json={"nickname": "Alex"})
        code = r.json()["code"]
        r2 = client.get(f"/api/rooms/{code}")
        assert r2.status_code == 200
        body = r2.json()
        assert body["code"] == code
        assert body["state"] == "lobby"
        assert len(body["players"]) == 1
        # Tokens must not appear in any public payload.
        assert "token" not in r2.text


def test_get_unknown_room_404() -> None:
    with TestClient(app) as client:
        r = client.get("/api/rooms/ZZZZZZ")
        assert r.status_code == 404
