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


def _drain_until(ws, types):  # type: ignore[no-untyped-def]
    """Read frames until we see one whose type is in `types`. Returns that frame."""
    for _ in range(20):
        msg = ws.receive_json()
        if msg["type"] in types:
            return msg
    raise AssertionError(f"never saw any of {types}")


def test_host_can_create_and_assign_teams() -> None:
    with TestClient(app) as client:
        code, host_id, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()  # snapshot
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()  # snapshot
                host_ws.receive_json()  # lobby/state from joiner connecting

                host_ws.send_json({"type": "lobby/team_create", "data": {"name": "Red"}})
                msg = _drain_until(joiner_ws, {"lobby/state"})
                teams = msg["data"]["teams"]
                assert len(teams) == 1
                assert teams[0]["name"] == "Red"
                team_id = teams[0]["id"]

                host_ws.receive_json()  # the same lobby/state landed at host too

                host_ws.send_json(
                    {
                        "type": "lobby/team_set",
                        "data": {"player_id": joiner_id, "team_id": team_id},
                    }
                )
                msg = _drain_until(joiner_ws, {"lobby/state"})
                players_by_id = {p["id"]: p for p in msg["data"]["players"]}
                assert players_by_id[joiner_id]["team_id"] == team_id


def test_non_host_cannot_create_team() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()  # lobby/state from connect

                joiner_ws.send_json({"type": "lobby/team_create", "data": {"name": "Red"}})
                err = _drain_until(joiner_ws, {"error"})
                assert err["data"]["code"] == "not_host"


def test_self_join_team_works_for_non_host() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                # Host creates a team.
                host_ws.send_json({"type": "lobby/team_create", "data": {"name": "Red"}})
                msg = _drain_until(joiner_ws, {"lobby/state"})
                team_id = msg["data"]["teams"][0]["id"]
                host_ws.receive_json()

                # Joiner moves themselves into it.
                joiner_ws.send_json(
                    {
                        "type": "lobby/team_set",
                        "data": {"player_id": joiner_id, "team_id": team_id},
                    }
                )
                msg = _drain_until(joiner_ws, {"lobby/state"})
                players_by_id = {p["id"]: p for p in msg["data"]["players"]}
                assert players_by_id[joiner_id]["team_id"] == team_id


def test_non_host_cannot_move_other_player() -> None:
    with TestClient(app) as client:
        code, host_id, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                host_ws.send_json({"type": "lobby/team_create", "data": {"name": "Red"}})
                msg = _drain_until(joiner_ws, {"lobby/state"})
                team_id = msg["data"]["teams"][0]["id"]
                host_ws.receive_json()

                joiner_ws.send_json(
                    {
                        "type": "lobby/team_set",
                        "data": {"player_id": host_id, "team_id": team_id},
                    }
                )
                err = _drain_until(joiner_ws, {"error"})
                assert err["data"]["code"] == "not_host"


def test_randomize_distributes_players() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _join_room(client, code, "Mira")
        _join_room(client, code, "Pat")
        _join_room(client, code, "Sam")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()  # snapshot
            host_ws.send_json({"type": "lobby/randomize_teams", "data": {"team_count": 2}})
            msg = _drain_until(host_ws, {"lobby/state"})
            teams = msg["data"]["teams"]
            assert len(teams) == 2
            total_assigned = sum(len(t["player_ids"]) for t in teams)
            assert total_assigned == 4


def test_host_updates_settings_broadcasts_to_everyone() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")

        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                host_ws.send_json(
                    {
                        "type": "lobby/settings_set",
                        "data": {"mode": "time", "time_seconds": 90},
                    }
                )
                msg = _drain_until(joiner_ws, {"lobby/state"})
                settings = msg["data"]["settings"]
                assert settings["mode"] == "time"
                assert settings["time_seconds"] == 90


def test_invalid_settings_returns_error() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            host_ws.send_json(
                {
                    "type": "lobby/settings_set",
                    "data": {"mode": "time", "time_seconds": 7},
                }
            )
            err = _drain_until(host_ws, {"error"})
            assert err["data"]["code"] == "bad_settings"
