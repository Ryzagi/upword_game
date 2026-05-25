from fastapi.testclient import TestClient

from app.main import app


def _create_room(client: TestClient, nickname: str) -> tuple[str, str, str]:
    r = client.post("/api/rooms", json={"nickname": nickname})
    body = r.json()
    return body["code"], body["player_id"], body["token"]


def _join_room(client: TestClient, code: str, nickname: str) -> tuple[str, str]:
    r = client.post(f"/api/rooms/{code}/join", json={"nickname": nickname})
    body = r.json()
    return body["player_id"], body["token"]


def test_ws_sends_snapshot_on_connect() -> None:
    with TestClient(app) as client:
        code, player_id, token = _create_room(client, "Alex")
        with client.websocket_connect(f"/ws/rooms/{code}?token={token}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "room/snapshot"
            data = msg["data"]
            assert data["code"] == code
            assert data["state"] == "lobby"
            assert data["your_player_id"] == player_id
            assert len(data["players"]) == 1


def test_ws_rejects_invalid_token() -> None:
    with TestClient(app) as client:
        code, _, _ = _create_room(client, "Alex")
        # TestClient surfaces a close-before-accept as WebSocketDisconnect
        # raised from the context manager entry. Catching is awkward; instead
        # connect with the wrong token and confirm the next receive fails.
        try:
            with client.websocket_connect(f"/ws/rooms/{code}?token=wrong") as ws:
                # If we somehow got in, the server should close immediately.
                with __import__("pytest").raises(Exception):
                    ws.receive_json()
        except Exception:
            pass


def test_ws_rejects_unknown_room() -> None:
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/rooms/ZZZZZZ?token=anything") as ws:
                with __import__("pytest").raises(Exception):
                    ws.receive_json()
        except Exception:
            pass


def test_two_clients_see_each_others_state() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            # Host gets snapshot
            host_snap = host_ws.receive_json()
            assert host_snap["type"] == "room/snapshot"
            # Host sees Mira already (she joined via HTTP but hasn't connected yet)
            nicks = {p["nickname"] for p in host_snap["data"]["players"]}
            assert nicks == {"Alex", "Mira"}

            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_snap = joiner_ws.receive_json()
                assert joiner_snap["type"] == "room/snapshot"

                # Host receives the lobby/state broadcast triggered by Mira connecting
                host_event = host_ws.receive_json()
                assert host_event["type"] == "lobby/state"
                connected = {
                    p["nickname"]: p["is_connected"] for p in host_event["data"]["players"]
                }
                assert connected["Mira"] is True


def test_rename_broadcasts_lobby_state() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()  # snapshot
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()  # snapshot
                host_ws.receive_json()  # lobby/state from joiner connecting

                joiner_ws.send_json({"type": "lobby/rename", "data": {"nickname": "Maya"}})

                # Both clients should receive lobby/state with the new nickname
                host_update = host_ws.receive_json()
                assert host_update["type"] == "lobby/state"
                nicks = {p["nickname"] for p in host_update["data"]["players"]}
                assert "Maya" in nicks
                assert "Mira" not in nicks


def test_rename_to_taken_nickname_errors_only_to_sender() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()  # snapshot
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()  # lobby/state from joiner connecting

                joiner_ws.send_json({"type": "lobby/rename", "data": {"nickname": "Alex"}})
                err = joiner_ws.receive_json()
                assert err["type"] == "error"
                assert err["data"]["code"] == "nickname_taken"


def test_disconnect_marks_player_disconnected() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token=" + host_token) as host_ws:
            host_ws.receive_json()  # snapshot

            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()  # snapshot
                host_ws.receive_json()  # lobby/state from joiner connecting

            host_msg = host_ws.receive_json()
            assert host_msg["type"] == "lobby/state", host_msg
            by_nick = {p["nickname"]: p for p in host_msg["data"]["players"]}
            assert by_nick["Mira"]["is_connected"] is False
