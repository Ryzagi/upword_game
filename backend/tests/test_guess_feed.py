"""Every non-empty guess is broadcast to all clients as a chat-style
`guess/feed` event with player + team + text + correctness, so a chat panel
can render attempts in real time."""

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
    raise AssertionError(f"never saw {types}")


def test_wrong_guess_broadcasts_chat_event() -> None:
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
                guesser_id = joiner_id if describer_id == host_id else host_id

                describer_ws.send_json(
                    {
                        "type": "round/pick_cell",
                        "data": {"theme_id": "sport", "difficulty": 1},
                    }
                )
                _drain_until(host_ws, {"round/started"})
                _drain_until(joiner_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

                guesser_ws.send_json({"type": "guess/submit", "data": {"text": "definitelynot"}})

                # Both clients should receive a guess/feed event for the
                # wrong guess (so a chat panel can render it).
                d_feed = _drain_until(describer_ws, {"guess/feed"})
                assert d_feed["data"]["player_id"] == guesser_id
                assert d_feed["data"]["correct"] is False
                assert d_feed["data"]["text"] == "definitelynot"
                g_feed = _drain_until(guesser_ws, {"guess/feed"})
                assert g_feed["data"] == d_feed["data"]


def test_correct_guess_also_broadcasts_chat_event() -> None:
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
                word = _drain_until(describer_ws, {"describer/word"})["data"]["word_text"]

                guesser_ws.send_json({"type": "guess/submit", "data": {"text": word}})

                feed = _drain_until(guesser_ws, {"guess/feed"})
                assert feed["data"]["correct"] is True
                # The secret word must NOT be echoed back in the chat —
                # other players are still trying to guess.
                assert feed["data"]["text"] == ""


def test_empty_guess_does_not_broadcast() -> None:
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

                # Whitespace-only guess: silently ignored. We send a
                # follow-up real guess and assert that *only one*
                # guess/feed lands.
                guesser_ws.send_json({"type": "guess/submit", "data": {"text": "   "}})
                guesser_ws.send_json({"type": "guess/submit", "data": {"text": "anyguess"}})
                feed = _drain_until(host_ws, {"guess/feed"})
                assert feed["data"]["text"] == "anyguess"
