from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.game.round import Round
from app.models.errors import DomainError, InvalidPayloadError, NotHostError
from app.rooms.manager import RoomManager
from app.rooms.room import Room

log = logging.getLogger(__name__)

router = APIRouter()

# Heartbeat tuning.
PING_AFTER = 20.0
IDLE_TIMEOUT = 60.0

# Time before evicting a hard-disconnected player from the room.
DISCONNECT_GRACE_SECONDS = 60.0

# Application-defined close codes (4xxx range).
CLOSE_ROOM_NOT_FOUND = 4404
CLOSE_INVALID_TOKEN = 4401
CLOSE_IDLE_TIMEOUT = 4408
CLOSE_REPLACED = 4000


@router.websocket("/rooms/{code}")
async def ws_room(ws: WebSocket, code: str, token: str = Query(...)) -> None:
    manager: RoomManager = ws.app.state.room_manager
    room = manager.get_room(code)
    if room is None:
        await ws.close(code=CLOSE_ROOM_NOT_FOUND, reason="room_not_found")
        return

    player_id = room.player_id_for_token(token)
    if player_id is None:
        await ws.close(code=CLOSE_INVALID_TOKEN, reason="invalid_token")
        return

    await ws.accept()
    await room.attach_connection(player_id, ws)

    try:
        await ws.send_json({"type": "room/snapshot", "data": _snapshot_for(room, player_id)})
        await room.broadcast(
            {"type": "lobby/state", "data": _lobby_state(room)},
            exclude={player_id},
        )
        await _recv_loop(ws, room, player_id)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws loop crashed for room=%s player=%s", code, player_id)
    finally:
        was_active = await room.detach_connection(player_id, ws)
        if was_active:
            asyncio.create_task(_post_disconnect(manager, room, player_id))


async def _recv_loop(ws: WebSocket, room: Room, player_id: str) -> None:
    """Read frames from `ws`. Pings on inactivity, drops after IDLE_TIMEOUT."""
    loop = asyncio.get_event_loop()
    last_activity = loop.time()
    while True:
        elapsed_since_activity = loop.time() - last_activity
        remaining_until_idle = IDLE_TIMEOUT - elapsed_since_activity
        if remaining_until_idle <= 0:
            await ws.close(code=CLOSE_IDLE_TIMEOUT, reason="idle_timeout")
            return
        wait_for = min(PING_AFTER, remaining_until_idle)
        try:
            frame = await asyncio.wait_for(ws.receive_json(), timeout=wait_for)
        except TimeoutError:
            try:
                await ws.send_json({"type": "server/ping"})
            except Exception:
                return
            continue
        last_activity = loop.time()
        await _dispatch(ws, room, player_id, frame)


# =========================================================== inbound dispatch


async def _dispatch(ws: WebSocket, room: Room, player_id: str, frame: Any) -> None:
    if not isinstance(frame, dict) or "type" not in frame:
        await _send_error(ws, "invalid_payload")
        return
    event_type = frame["type"]
    data = frame.get("data") or {}
    try:
        # --- low-level / lobby ---
        if event_type == "client/pong":
            return
        if event_type == "lobby/rename":
            await _handle_rename(room, player_id, data)
            return
        # --- team management ---
        if event_type == "lobby/team_create":
            _require_host(room, player_id)
            await _handle_team_create(room, data)
            return
        if event_type == "lobby/team_delete":
            _require_host(room, player_id)
            await _handle_team_delete(room, data)
            return
        if event_type == "lobby/team_rename":
            _require_host(room, player_id)
            await _handle_team_rename(room, data)
            return
        if event_type == "lobby/team_set":
            await _handle_team_set(room, player_id, data)
            return
        if event_type == "lobby/randomize_teams":
            _require_host(room, player_id)
            await _handle_randomize_teams(room, data)
            return
        if event_type == "lobby/settings_set":
            _require_host(room, player_id)
            await _handle_settings_set(room, data)
            return
        if event_type == "lobby/theme_picks_set":
            await _handle_theme_picks_set(room, player_id, data)
            return
        if event_type == "lobby/theme_generate":
            await _handle_theme_generate(ws, room, player_id, data)
            return
        # --- game flow ---
        if event_type == "lobby/start_game":
            _require_host(room, player_id)
            await _handle_start_game(room)
            return
        if event_type == "round/pick_cell":
            await _handle_pick_cell(room, player_id, data)
            return
        if event_type == "round/concede":
            await _handle_concede(room, player_id)
            return
        if event_type == "round/force_end":
            _require_host(room, player_id)
            await _handle_force_end(room)
            return
        if event_type == "game/play_again":
            _require_host(room, player_id)
            await _handle_play_again(room)
            return
        # --- live round events ---
        if event_type == "describer/text":
            await _handle_describer_text(room, player_id, data)
            return
        if event_type == "guess/submit":
            await _handle_guess_submit(room, player_id, data)
            return
        if event_type == "reaction/toggle":
            await _handle_reaction_toggle(room, player_id, data)
            return
        await _send_error(ws, "invalid_payload", ref=event_type)
    except DomainError as e:
        await _send_error(ws, e.code, ref=event_type)
    except ValueError as e:
        await _send_error(ws, str(e), ref=event_type)


def _require_host(room: Room, player_id: str) -> None:
    if not room.is_host(player_id):
        raise NotHostError()


# ====================================================== lobby event handlers


async def _handle_rename(room: Room, player_id: str, data: dict[str, Any]) -> None:
    nickname = data.get("nickname")
    if not isinstance(nickname, str):
        raise InvalidPayloadError()
    await room.rename_player(player_id, nickname)
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


async def _handle_team_create(room: Room, data: dict[str, Any]) -> None:
    name = data.get("name")
    if not isinstance(name, str):
        raise InvalidPayloadError()
    await room.create_team(name)
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


async def _handle_team_delete(room: Room, data: dict[str, Any]) -> None:
    team_id = data.get("team_id")
    if not isinstance(team_id, str):
        raise InvalidPayloadError()
    await room.delete_team(team_id)
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


async def _handle_team_rename(room: Room, data: dict[str, Any]) -> None:
    team_id = data.get("team_id")
    name = data.get("name")
    if not isinstance(team_id, str) or not isinstance(name, str):
        raise InvalidPayloadError()
    await room.rename_team(team_id, name)
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


async def _handle_team_set(room: Room, player_id: str, data: dict[str, Any]) -> None:
    target_player_id = data.get("player_id")
    team_id = data.get("team_id")
    if not isinstance(target_player_id, str):
        raise InvalidPayloadError()
    if team_id is not None and not isinstance(team_id, str):
        raise InvalidPayloadError()
    if target_player_id != player_id and not room.is_host(player_id):
        raise NotHostError()
    await room.set_player_team(target_player_id, team_id)
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


async def _handle_randomize_teams(room: Room, data: dict[str, Any]) -> None:
    team_count = data.get("team_count")
    if not isinstance(team_count, int):
        raise InvalidPayloadError()
    await room.randomize_teams(team_count)
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


async def _handle_theme_picks_set(
    room: Room, player_id: str, data: dict[str, Any]
) -> None:
    theme_ids = data.get("theme_ids")
    if not isinstance(theme_ids, list):
        raise InvalidPayloadError()
    await room.set_player_theme_picks(player_id, [str(t) for t in theme_ids])
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


async def _handle_theme_generate(
    ws: WebSocket, room: Room, player_id: str, data: dict[str, Any]
) -> None:
    """Player asks for a new AI-generated theme. The generator call happens
    OUTSIDE the room lock (it's a multi-second HTTP round-trip) — we hold
    the lock only for the cooldown/cap check up front and for the append
    at the end. The generator itself is idempotent; the only race we care
    about is two players both blowing through the cap simultaneously, which
    the second lock acquisition catches."""
    from app.ai.theme_generator import ThemeGenerationError
    from app.models.errors import (
        ThemeGenCapReachedError,
        ThemeGenFailedError,
        ThemeGenInvalidPromptError,
        ThemeGenRateLimitedError,
        ThemeGenUnavailableError,
    )

    generator = getattr(ws.app.state, "theme_generator", None)
    if generator is None:
        raise ThemeGenUnavailableError()

    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ThemeGenInvalidPromptError()
    clean_prompt = prompt.strip()[:120]

    async with room.lock:
        allowed, err_code = room.can_generate_theme_locked(player_id)
        if not allowed:
            if err_code == "theme_gen_rate_limited":
                raise ThemeGenRateLimitedError()
            if err_code == "theme_gen_cap_reached":
                raise ThemeGenCapReachedError()
            raise ThemeGenFailedError()
        existing_ids = room._all_theme_ids_locked()  # noqa: SLF001
        language = room.language

    # Heavy call — outside the lock.
    try:
        theme = await generator.generate(
            prompt=clean_prompt,
            language=language,
            existing_theme_ids=existing_ids,
        )
    except ThemeGenerationError as e:
        log.info("theme generation failed: %s", e)
        if str(e) == "invalid_prompt":
            raise ThemeGenInvalidPromptError() from e
        raise ThemeGenFailedError() from e
    except Exception as e:
        log.warning("theme generation crashed: %s", e)
        raise ThemeGenFailedError() from e

    # Re-acquire the lock and re-check the cap (someone else may have
    # generated theirs while ours was in flight).
    async with room.lock:
        if len(room.extra_themes) >= 5:
            raise ThemeGenCapReachedError()
        # ID collision can happen when two players generate concurrently
        # and OpenAI produces similar names — both snapshots saw the same
        # existing_ids set, so both synthesised the same `ai-<slug>` id.
        # Resolve in-flight by appending a short random suffix; don't fail
        # the second player just because they were a few ms behind.
        if theme.id in room._all_theme_ids_locked():  # noqa: SLF001
            import secrets

            existing = room._all_theme_ids_locked()  # noqa: SLF001
            base = theme.id
            for _ in range(8):
                candidate = f"{base}-{secrets.token_hex(2)}"
                if candidate not in existing:
                    theme = theme.model_copy(update={"id": candidate})
                    break
            else:
                # Wildly unlucky — give up.
                raise ThemeGenFailedError()
        room.add_generated_theme(theme, player_id)
        snapshot_corpus = [
            {
                "id": t.id,
                "name": t.name,
                "icon": t.icon,
                "generated_by": room.theme_generators.get(t.id),
            }
            for t in room._all_themes_locked()  # noqa: SLF001
        ]

    await room.broadcast(
        {
            "type": "lobby/theme_added",
            "data": {
                "theme": {
                    "id": theme.id,
                    "name": theme.name,
                    "icon": theme.icon,
                    "generated_by": player_id,
                },
                "corpus_themes": snapshot_corpus,
            },
        }
    )


async def _handle_settings_set(room: Room, data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise InvalidPayloadError()
    await room.update_settings(data)
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


# ===================================================== game-flow handlers


async def _handle_start_game(room: Room) -> None:
    await room.start_game()
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})
    await room.broadcast(
        {
            "type": "game/started",
            "data": {
                "board": room.board.public() if room.board else None,
                "scoreboard": room.scoreboard(),
                "describer_queue": list(room.rotation),
                "current_describer_id": room.current_describer_id,
            },
        }
    )


async def _handle_pick_cell(room: Room, player_id: str, data: dict[str, Any]) -> None:
    theme_id = data.get("theme_id")
    difficulty = data.get("difficulty")
    if not isinstance(theme_id, str) or not isinstance(difficulty, int):
        raise InvalidPayloadError()
    round_obj = await room.pick_cell(player_id, theme_id, difficulty)
    await room.broadcast({"type": "round/started", "data": round_obj.public()})
    await room.send_to(
        round_obj.describer_id,
        {"type": "describer/word", "data": round_obj.private()},
    )
    # Schedule the time-mode timer if the round has a deadline.
    if round_obj.ends_at is not None:
        delay = (round_obj.ends_at - datetime.now(UTC)).total_seconds()
        if delay > 0:
            room._round_end_task = asyncio.create_task(  # noqa: SLF001
                _round_timer_task(room, round_obj.id, delay)
            )
    # Start the letter-reveal drip so outsiders get a hint every 15 s.
    room._letter_reveal_task = asyncio.create_task(  # noqa: SLF001
        _letter_reveal_task(room, round_obj.id)
    )


async def _handle_concede(room: Room, player_id: str) -> None:
    ended = await room.concede(player_id)
    await _emit_round_ended(room, ended, conceded=True, forced=False)


async def _handle_force_end(room: Room) -> None:
    ended = await room.force_end_round()
    await _emit_round_ended(room, ended, conceded=False, forced=True)


async def _handle_play_again(room: Room) -> None:
    """Reset the game back to the lobby (post-ended). Clients see a
    `lobby/state` with state=lobby; the EndedView unmounts and the lobby
    picker is shown again."""
    await room.play_again()
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})


# ----------------------------------------------------- live-round handlers


async def _handle_describer_text(room: Room, player_id: str, data: dict[str, Any]) -> None:
    text = data.get("text")
    if not isinstance(text, str):
        raise InvalidPayloadError()
    await room.set_describer_text(player_id, text)


async def _handle_reaction_toggle(room: Room, player_id: str, data: dict[str, Any]) -> None:
    kind = data.get("kind")
    if kind not in ("like", "dislike"):
        raise InvalidPayloadError()
    state = await room.toggle_reaction(player_id, kind)
    await room.broadcast({"type": "reaction/state", "data": state})


async def _handle_guess_submit(room: Room, player_id: str, data: dict[str, Any]) -> None:
    text = data.get("text")
    if not isinstance(text, str):
        raise InvalidPayloadError()
    result = await room.submit_guess(player_id, text)
    if result.empty:
        return
    # Broadcast the guess as a chat-style message visible to everyone.
    # Capped to avoid pathological lengths in the chat feed.
    # For a correct guess we redact the body — clients only need to know
    # someone got it, not what the secret word was (would spoil it for
    # players who haven't guessed yet).
    chat_text = "" if result.correct else text.strip()[:120]
    await room.broadcast(
        {
            "type": "guess/feed",
            "data": {
                "player_id": player_id,
                "team_id": result.team_id,
                "text": chat_text,
                "correct": result.correct,
                "at": datetime.now(UTC).isoformat(),
            },
        }
    )
    if result.penalty_applied:
        await room.send_to(
            player_id,
            {
                "type": "guess/penalty",
                "data": {
                    "amount": result.penalty_applied,
                    "new_balance": result.new_team_score,
                },
            },
        )
    if result.correct:
        await room.broadcast(
            {
                "type": "guess/correct",
                "data": {
                    "player_id": player_id,
                    "team_id": result.team_id,
                    "position": result.team_position,
                    "points_awarded": result.team_points,
                    "total_team_score": result.new_team_score,
                },
            }
        )
    else:
        await room.send_to(
            player_id,
            {
                "type": "guess/wrong",
                "data": {
                    "free_attempts_left": result.free_attempts_left,
                    "paid_attempts_total": result.paid_attempts_total,
                },
            },
        )
    if result.round_ended is not None:
        await _emit_round_ended(room, result.round_ended, conceded=False, forced=False)


# ---------------------------------------------------- timer task


async def _letter_reveal_task(room: Room, round_id: str) -> None:
    """Every LETTER_REVEAL_INTERVAL seconds, uncover one random un-revealed
    non-whitespace index in the secret word and broadcast the new pattern.
    Runs until either the round ends or every letter is revealed."""
    import random as _random

    from app.rooms.room import LETTER_REVEAL_INTERVAL_SECONDS

    while True:
        try:
            await asyncio.sleep(LETTER_REVEAL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return
        async with room.lock:
            if room.current_round is None or room.current_round.id != round_id:
                return
            round_obj = room.current_round
            hidden = round_obj.hidden_letter_indices()
            if not hidden:
                room._letter_reveal_task = None  # noqa: SLF001
                return
            chosen = _random.choice(hidden)
            round_obj.revealed_indices.add(chosen)
            pattern = round_obj.letter_pattern()
            revealed = sorted(round_obj.revealed_indices)
            done = not round_obj.hidden_letter_indices()
        await room.broadcast(
            {
                "type": "round/letter_reveal",
                "data": {
                    "revealed_indices": revealed,
                    "pattern": pattern,
                },
            }
        )
        if done:
            return


async def _round_timer_task(room: Room, round_id: str, delay: float) -> None:
    """Wait until the round's deadline, then force-end it if still active."""
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return
    # Re-check that we're still timing the same round.
    if room.current_round is None or room.current_round.id != round_id:
        return
    try:
        ended = await room.force_end_round()
    except DomainError:
        return
    await _emit_round_ended(room, ended, conceded=False, forced=False, reason="time_expired")


# =================================================== disconnect / eviction


async def _post_disconnect(manager: RoomManager, room: Room, player_id: str) -> None:
    """First broadcast the connection drop, then evict after the grace period."""
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})
    await asyncio.sleep(DISCONNECT_GRACE_SECONDS)
    async with room.lock:
        player = room.players.get(player_id)
        still_disconnected = player is not None and not player.is_connected
    if not still_disconnected:
        return
    result = await room.remove_player(player_id)
    await room.broadcast({"type": "lobby/player_left", "data": {"player_id": player_id}})
    await room.broadcast({"type": "lobby/state", "data": _lobby_state(room)})
    if result.round_ended is not None:
        await _emit_round_ended(room, result.round_ended, conceded=False, forced=True)
    if room.is_empty():
        await manager.drop_room_if_empty(room.code)


# ============================================================ helpers


async def _emit_round_ended(
    room: Room,
    ended: Round,
    *,
    conceded: bool = False,
    forced: bool = False,
    reason: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "round_id": ended.id,
        "describer_id": ended.describer_id,
        "theme_id": ended.theme_id,
        "difficulty": ended.difficulty,
        "base_score": ended.base_score,
        "word_text": ended.word_text,
        "hint": ended.hint,
        "conceded": conceded,
        "forced": forced,
        "results": ended.results or {},
    }
    if reason is not None:
        payload["reason"] = reason
    await room.broadcast({"type": "round/ended", "data": payload})
    await _emit_post_round(room)


async def _emit_post_round(room: Room) -> None:
    if room.state == "ended":
        await room.broadcast(
            {
                "type": "game/ended",
                "data": {"final_scores": room.scoreboard()},
            }
        )
    else:
        await room.broadcast(
            {
                "type": "board/state",
                "data": {
                    "board": room.board.public() if room.board else None,
                    "scoreboard": room.scoreboard(),
                    "current_describer_id": room.current_describer_id,
                },
            }
        )


# ============================================================ serialisation


def _lobby_state(room: Room) -> dict[str, object]:
    from app.rooms.room import _max_picks_per_player

    return {
        "host_id": room.host_id,
        "players": [p.public() for p in room.players.values()],
        "teams": [
            t.public([pid for pid, p in room.players.items() if p.team_id == t.id])
            for t in room.teams.values()
        ],
        "settings": room.settings.model_dump(),
        "state": room.state,
        "max_theme_picks_per_player": _max_picks_per_player(len(room.players)),
    }


def _snapshot_for(room: Room, your_player_id: str) -> dict[str, object]:
    snapshot = room.snapshot()
    snapshot["your_player_id"] = your_player_id
    private = room.private_round_info_for(your_player_id)
    if private is not None:
        snapshot["your_describer_word"] = private
    state = room.private_round_state_for(your_player_id)
    if state is not None:
        snapshot["your_round_state"] = state
    return snapshot


async def _send_error(ws: WebSocket, code: str, *, ref: str | None = None) -> None:
    payload: dict[str, object] = {"code": code}
    if ref is not None:
        payload["ref"] = ref
    try:
        await ws.send_json({"type": "error", "data": payload})
    except Exception:
        pass
