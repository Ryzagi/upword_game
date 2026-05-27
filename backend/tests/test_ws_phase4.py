"""Phase 4 — WebSocket integration tests for the live round flow."""

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


def _start_two_player_game(client: TestClient):
    """Create a room, start a game, return (host_ws, joiner_ws, describer_ws, guesser_ws,
    describer_token, guesser_token, describer_player_id) inside a context."""
    code, host_id, host_token = _create_room(client, "Alex")
    joiner_id, joiner_token = _join_room(client, code, "Mira")
    return code, host_id, host_token, joiner_id, joiner_token


# ----------------------------------------------------- describer/text broadcast


def test_describer_text_broadcasts_to_other_players() -> None:
    with TestClient(app) as client:
        code, host_id, host_token, joiner_id, joiner_token = _start_two_player_game(client)
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
                _drain_until(guesser_ws, {"round/started"})
                _drain_until(describer_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

                describer_ws.send_json(
                    {"type": "describer/text", "data": {"text": "a round object…"}}
                )

                msg = _drain_until(guesser_ws, {"describer/text"})
                assert msg["data"]["text"] == "a round object…"


def test_describer_text_rejected_for_non_describer() -> None:
    with TestClient(app) as client:
        code, host_id, host_token, joiner_id, joiner_token = _start_two_player_game(client)
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
                _drain_until(guesser_ws, {"round/started"})
                _drain_until(describer_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

                guesser_ws.send_json({"type": "describer/text", "data": {"text": "cheating"}})
                err = _drain_until(guesser_ws, {"error"})
                assert err["data"]["code"] == "not_describer"


# ----------------------------------------------------- guess flow


def test_correct_guess_broadcasts_guess_correct_and_auto_ends_round() -> None:
    with TestClient(app) as client:
        code, host_id, host_token, joiner_id, joiner_token = _start_two_player_game(client)
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
                _drain_until(guesser_ws, {"round/started"})
                _drain_until(describer_ws, {"round/started"})
                word_event = _drain_until(describer_ws, {"describer/word"})
                target_word = word_event["data"]["word_text"]

                guesser_ws.send_json({"type": "guess/submit", "data": {"text": target_word}})

                # Broadcast guess/correct lands on both sides.
                gc_guesser = _drain_until(guesser_ws, {"guess/correct"})
                assert gc_guesser["data"]["position"] == 1
                assert gc_guesser["data"]["points_awarded"] == 100
                gc_describer = _drain_until(describer_ws, {"guess/correct"})
                assert gc_describer["data"]["position"] == 1

                # Auto-end → round/ended + board/state.
                ended = _drain_until(guesser_ws, {"round/ended"})
                assert ended["data"]["conceded"] is False
                assert ended["data"]["forced"] is False
                results = ended["data"]["results"]
                # describer reward at base 100, k=1 → floor(100 * 0.5) = 50
                assert results["describer_points"] == 50
                _drain_until(guesser_ws, {"board/state"})


def test_wrong_guess_returns_private_event() -> None:
    with TestClient(app) as client:
        code, host_id, host_token, joiner_id, joiner_token = _start_two_player_game(client)
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()
                host_ws.send_json({"type": "lobby/start_game", "data": {}})
                # In attempts mode by default, so the wrong/attempts paths work.
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
                _drain_until(guesser_ws, {"round/started"})
                _drain_until(describer_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

                guesser_ws.send_json({"type": "guess/submit", "data": {"text": "definitelynot"}})
                # Private to submitter.
                wrong = _drain_until(guesser_ws, {"guess/wrong"})
                assert wrong["data"]["free_attempts_left"] == 4  # default 5 → 4 left
                assert wrong["data"]["paid_attempts_total"] == 0


def test_attempts_mode_penalty_after_free_exhausted() -> None:
    with TestClient(app) as client:
        code, host_id, host_token, joiner_id, joiner_token = _start_two_player_game(client)
        with client.websocket_connect(f"/ws/rooms/{code}?token={host_token}") as host_ws:
            host_ws.receive_json()
            with client.websocket_connect(f"/ws/rooms/{code}?token={joiner_token}") as joiner_ws:
                joiner_ws.receive_json()
                host_ws.receive_json()

                # Set attempts to 1 so we hit the paid path quickly.
                host_ws.send_json(
                    {
                        "type": "lobby/settings_set",
                        "data": {"mode": "attempts", "attempts_per_round": 1},
                    }
                )
                _drain_until(joiner_ws, {"lobby/state"})
                _drain_until(host_ws, {"lobby/state"})

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
                _drain_until(guesser_ws, {"round/started"})
                _drain_until(describer_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

                # First wrong guess uses the free attempt.
                guesser_ws.send_json({"type": "guess/submit", "data": {"text": "nope"}})
                w1 = _drain_until(guesser_ws, {"guess/wrong"})
                assert w1["data"]["free_attempts_left"] == 0
                assert w1["data"]["paid_attempts_total"] == 0

                # Second wrong guess: paid attempt, -10 penalty. The handler
                # now also broadcasts guess/feed for chat, so the guesser's
                # outbox holds three frames: guess/feed, guess/penalty, guess/wrong.
                guesser_ws.send_json({"type": "guess/submit", "data": {"text": "stillnope"}})
                events = [
                    guesser_ws.receive_json(),
                    guesser_ws.receive_json(),
                    guesser_ws.receive_json(),
                ]
                kinds = {e["type"] for e in events}
                assert kinds == {"guess/feed", "guess/penalty", "guess/wrong"}
                penalty = next(e for e in events if e["type"] == "guess/penalty")
                assert penalty["data"]["amount"] == 10


def test_describer_cannot_guess_via_ws() -> None:
    with TestClient(app) as client:
        code, host_id, host_token, joiner_id, joiner_token = _start_two_player_game(client)
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
                _drain_until(describer_ws, {"round/started"})
                _drain_until(describer_ws, {"describer/word"})

                describer_ws.send_json({"type": "guess/submit", "data": {"text": "ball"}})
                err = _drain_until(describer_ws, {"error"})
                assert err["data"]["code"] == "describer_cannot_guess"


def test_round_ended_payload_includes_results() -> None:
    with TestClient(app) as client:
        code, host_id, host_token, joiner_id, joiner_token = _start_two_player_game(client)
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
                _drain_until(describer_ws, {"describer/word"})

                # Force-end with no guesses; results should report 0 reward + no per_team winners.
                host_ws.send_json({"type": "round/force_end", "data": {}})
                ended = _drain_until(host_ws, {"round/ended"})
                results = ended["data"]["results"]
                assert results["describer_points"] == 0
                assert all(row["position"] is None for row in results["per_team"])
