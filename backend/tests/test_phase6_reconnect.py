"""Phase 6 — mid-round reconnect snapshot tests.

A player closes their WS and re-opens it during an active round. The
`room/snapshot` they receive on the new connection must restore enough state
that the UI continues seamlessly:

  - everyone: current_round (with live_text + reactions)
  - describer: word + hint via `your_describer_word`
  - guesser: attempt budget via `your_round_state`
"""

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


def _drain_until(ws: Any, types: set[str], limit: int = 30) -> dict[str, Any]:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] in types:
            return msg
    raise AssertionError(f"never saw any of {types}")


def _start_round(client, host_id, host_token, joiner_token):  # type: ignore[no-untyped-def]
    """Connect host + joiner, start a game, pick Sport·1. Returns the role/token
    assignment plus the describer's word."""
    code = host_token  # never used directly here
    # Open both, start the round.
    host_ws_cm = client.websocket_connect(f"/ws/rooms/{code}?token={host_token}")
    # Caller passes the actual code; we work that out from a join below.
    return host_ws_cm


def test_reconnect_describer_snapshot_carries_word_and_round() -> None:
    with TestClient(app) as client:
        code, host_id, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()  # lobby/state from joiner connect
                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                _drain_until(joiner_ws, {"game/started"})
                describer_id = started["data"]["current_describer_id"]
                describer_ws = host_ws if describer_id == host_id else joiner_ws
                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 3},
                    }
                )
                _drain_until(host_ws, {"round/started"})
                _drain_until(joiner_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

        # Phase B: reconnect describer.
        describer_token = host_token if describer_id == host_id else joiner_token
        with client.websocket_connect(f"/ws/rooms/{code}?token={describer_token}") as describer_ws:
            snap = describer_ws.receive_json()
            assert snap["type"] == "room/snapshot"
            assert "current_round" in snap["data"]
            assert "your_describer_word" in snap["data"]
            assert snap["data"]["your_describer_word"]["word_text"]
            # describer doesn't get round_state (no attempts charged to describer)
            assert snap["data"]["state"] == "round"


def test_reconnect_guesser_snapshot_carries_attempts_and_no_word() -> None:
    with TestClient(app) as client:
        code, host_id, host_token = _create_room(client, "Alex")
        joiner_id, joiner_token = _join_room(client, code, "Mira")
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()
                # Set attempts to 3 to make the assertion crisp.
                host_ws.send_json(
                    {
                        "type": "lobby/settings_set",
                        "data": {"mode": "attempts", "attempts_per_round": 3},
                    }
                )
                _drain_until(host_ws, {"lobby/state"})
                _drain_until(joiner_ws, {"lobby/state"})
                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                started = _drain_until(host_ws, {"game/started"})
                _drain_until(joiner_ws, {"game/started"})
                describer_id = started["data"]["current_describer_id"]
                describer_ws = host_ws if describer_id == host_id else joiner_ws
                guesser_ws = joiner_ws if describer_id == host_id else host_ws
                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )
                _drain_until(host_ws, {"round/started"})
                _drain_until(joiner_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})
                # Guesser burns one attempt with a wrong guess.
                guesser_ws.send_json({"type": "guess/submit", "data": {"text": "definitelynot"}})
                _drain_until(guesser_ws, {"guess/wrong"})

        # Phase B: reconnect guesser.
        guesser_token = joiner_token if describer_id == host_id else host_token
        with client.websocket_connect(f"/ws/rooms/{code}?token={guesser_token}") as guesser_ws:
            snap = guesser_ws.receive_json()
            assert snap["type"] == "room/snapshot"
            # Guesser must NOT receive the word.
            assert "your_describer_word" not in snap["data"]
            # Guesser DOES receive their per-round state.
            rs = snap["data"]["your_round_state"]
            assert rs["free_attempts_left"] == 2  # 3 - 1 used
            assert rs["paid_attempts_total"] == 0
            assert rs["you_have_guessed_correctly"] is False


def test_reconnect_snapshot_preserves_reactions_and_live_text() -> None:
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
                describer_id = started["data"]["current_describer_id"]
                describer_ws = host_ws if describer_id == host_id else joiner_ws
                guesser_ws = joiner_ws if describer_id == host_id else host_ws
                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )
                _drain_until(host_ws, {"round/started"})
                _drain_until(joiner_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})
                # Describer types something
                describer_ws.send_json(
                    {"type": "describer/text", "data": {"text": "round and bouncy"}}
                )
                _drain_until(guesser_ws, {"describer/text"})
                # Guesser likes
                guesser_ws.send_json({"type": "reaction/toggle", "data": {"kind": "like"}})
                _drain_until(host_ws, {"reaction/state"})

        # Reconnect — both clients should see live_text + reactions in their snapshot.
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as ws:
            snap = ws.receive_json()
            assert snap["type"] == "room/snapshot"
            cr = snap["data"]["current_round"]
            assert cr["live_text"] == "round and bouncy"
            assert cr["reactions"]["likes"]  # at least one liker
