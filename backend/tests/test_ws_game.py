"""Phase 3 — WebSocket integration tests for the game flow."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


def _create_room(client: TestClient, nickname: str) -> tuple[str, str, str]:
    r = client.post("/api/rooms", json={"nickname": nickname, "language": "en"})
    body = r.json()
    return body["code"], body["player_id"], body["token"]


def _join_room(client: TestClient, code: str, nickname: str) -> tuple[str, str]:
    r = client.post(f"/api/rooms/{code}/join", json={"nickname": nickname})
    body = r.json()
    return body["player_id"], body["token"]


def _drain_until(ws: Any, types: set[str], limit: int = 50) -> dict[str, Any]:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] in types:
            return msg
    raise AssertionError(f"never saw any of {types} in {limit} frames")


# ----------------------------------------------------------- start_game


def test_non_host_cannot_start_game() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        _, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                joiner_ws.send_json({"type": "lobby/start_game", "data": {}})
                err = _drain_until(joiner_ws, {"error"})
                assert err["data"]["code"] == "not_host"


def test_start_game_fails_with_one_player() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            host_ws.send_json({"type": "lobby/start_game", "data": {}})
            err = _drain_until(host_ws, {"error"})
            assert err["data"]["code"] == "not_enough_players"


def test_start_game_solo_creates_teams_and_broadcasts() -> None:
    with TestClient(app) as client:
        code, host_id, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()  # snapshot
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()  # lobby/state from joiner connect

                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                game_started = _drain_until(joiner_ws, {"game/started"})
                data = game_started["data"]
                assert data["board"]["used"] == []
                assert {host_id, joiner_id} == set(data["describer_queue"])
                assert data["current_describer_id"] in {host_id, joiner_id}
                # Two teams (solo creates one per player)
                assert len(data["scoreboard"]) == 2


# ----------------------------------------------------- pick_cell visibility


def test_pick_cell_broadcasts_public_round_and_private_word_to_describer() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                describer_id = started["data"]["current_describer_id"]
                _drain_until(joiner_ws, {"game/started"})

                # Find which ws belongs to the describer.
                describer_ws = host_ws if describer_id != joiner_id else joiner_ws
                guesser_ws = joiner_ws if describer_id != joiner_id else host_ws

                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )

                # Both should see round/started (public, no word).
                guesser_round = _drain_until(guesser_ws, {"round/started"})
                assert "word_text" not in guesser_round["data"]
                assert guesser_round["data"]["describer_id"] == describer_id

                # The describer gets round/started (from the broadcast) and
                # describer/word (from the private send_to). Two frames.
                first = describer_ws.receive_json()
                second = describer_ws.receive_json()
                kinds = {first["type"], second["type"]}
                assert kinds == {"round/started", "describer/word"}
                describer_event = first if first["type"] == "describer/word" else second
                assert "word_text" in describer_event["data"]
                assert "hint" in describer_event["data"]


def test_non_describer_cannot_pick_cell() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                describer_id = started["data"]["current_describer_id"]
                _drain_until(joiner_ws, {"game/started"})

                non_describer_ws = host_ws if describer_id == joiner_id else joiner_ws
                non_describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )
                err = _drain_until(non_describer_ws, {"error"})
                assert err["data"]["code"] == "not_describer"


# ----------------------------------------------------- concede + board cycle


def test_concede_emits_round_ended_and_board_state() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                _drain_until(joiner_ws, {"game/started"})
                describer_id = started["data"]["current_describer_id"]
                describer_ws = host_ws if describer_id != joiner_id else joiner_ws
                guesser_ws = joiner_ws if describer_id != joiner_id else host_ws

                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )
                _drain_until(guesser_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

                describer_ws.send_json({"type": "round/concede", "data": {}})
                ended = _drain_until(guesser_ws, {"round/ended"})
                assert ended["data"]["conceded"] is True
                assert "word_text" in ended["data"]
                board_state = _drain_until(guesser_ws, {"board/state"})
                assert board_state["data"]["board"]["used"] == [
                    {"theme_id": "sport", "difficulty": 1}
                ]
                # next describer advanced
                assert board_state["data"]["current_describer_id"] != describer_id


def test_host_can_force_end_round() -> None:
    with TestClient(app) as client:
        code, _, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                _drain_until(joiner_ws, {"game/started"})
                describer_id = started["data"]["current_describer_id"]
                describer_ws = host_ws if describer_id != joiner_id else joiner_ws

                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )
                _drain_until(host_ws, {"round/started"})

                host_ws.send_json({"type": "round/force_end", "data": {}})
                ended = _drain_until(host_ws, {"round/ended"})
                assert ended["data"]["forced"] is True
                assert ended["data"]["conceded"] is False


# ------------------------------------------------- reconnect mid-round snapshot


def test_describer_snapshot_carries_word_on_reconnect() -> None:
    """Reconnect both clients while a round is active; the describer's
    snapshot must contain the word and the guesser's must not."""
    with TestClient(app) as client:
        code, host_id, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")

        # Phase A: open both, start game, pick a cell, then close both.
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()
                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                _drain_until(joiner_ws, {"game/started"})
                describer_id = started["data"]["current_describer_id"]
                describer_ws = host_ws if describer_id == host_id else joiner_ws
                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )
                _drain_until(host_ws, {"round/started"})
                _drain_until(joiner_ws, {"round/started"})

        # Phase B: reconnect each and inspect the snapshot.
        describer_token = host_token if describer_id == host_id else joiner_token
        guesser_token = joiner_token if describer_id == host_id else host_token

        with client.websocket_connect(f"/ws/rooms/{code}?token={describer_token}") as desc_ws:
            snap = desc_ws.receive_json()
            assert snap["type"] == "room/snapshot"
            assert "your_describer_word" in snap["data"]

        with client.websocket_connect(f"/ws/rooms/{code}?token={guesser_token}") as guess_ws:
            snap = guess_ws.receive_json()
            assert snap["type"] == "room/snapshot"
            assert "your_describer_word" not in snap["data"]


# ------------------------------------------------------------- play_again


def test_play_again_after_board_exhausted() -> None:
    with TestClient(app) as client:
        code, host_id, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()
                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                _drain_until(joiner_ws, {"game/started"})
                board = started["data"]["board"]
                theme_ids: list[str] = [t["id"] for t in board["themes"]]
                difficulties = range(1, len(board["base_values"]) + 1)

                # Play through every cell quickly: pick + concede.
                current_describer = started["data"]["current_describer_id"]
                describer_ws_of = lambda pid: host_ws if pid == host_id else joiner_ws  # noqa: E731

                for theme_id in theme_ids:
                    for difficulty in difficulties:
                        d_ws = describer_ws_of(current_describer)
                        d_ws.send_json(
                            {
                                "type": "round/pick_cell",
                                "data": {
                                    "theme_id": theme_id,
                                    "difficulty": difficulty,
                                },
                            }
                        )
                        # drain non-board frames
                        _drain_until(host_ws, {"round/started"})
                        _drain_until(joiner_ws, {"round/started"})
                        try:
                            _drain_until(d_ws, {"describer/word"})
                        except AssertionError:
                            pass
                        d_ws.send_json({"type": "round/concede", "data": {}})
                        _drain_until(host_ws, {"round/ended"})
                        _drain_until(joiner_ws, {"round/ended"})
                        # Next we expect either board/state (continuing) or
                        # game/ended (final cell).
                        nxt = _drain_until(host_ws, {"board/state", "game/ended"})
                        _drain_until(joiner_ws, {"board/state", "game/ended"})
                        if nxt["type"] == "game/ended":
                            current_describer = None  # game over
                        else:
                            current_describer = nxt["data"]["current_describer_id"]

                # The game has ended.
                host_ws.send_json({"type": "game/play_again", "data": {}})
                restarted = _drain_until(host_ws, {"game/started"})
                assert restarted["data"]["board"]["used"] == []
                for entry in restarted["data"]["scoreboard"]:
                    assert entry["score"] == 0
