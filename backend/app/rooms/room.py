from __future__ import annotations

import asyncio
import logging
import random
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from app.corpus.loader import normalise
from app.corpus.schema import Corpus, Theme
from app.game.board import Board
from app.game.rotation import compute_rotation
from app.game.round import CorrectTeamEntry, Round
from app.game.scoring import describer_reward, points_for_team_position
from app.game.word_picker import pick_word_for_cell
from app.models.errors import (
    AlreadyGuessedCorrectlyError,
    BadTeamConfigError,
    BadThemePicksError,
    CellAlreadyUsedError,
    DescriberCannotGuessError,
    InvalidTokenError,
    NicknameTakenError,
    NotDescriberError,
    NotEnoughPlayersError,
    NoWordsAvailableError,
    RoomFullError,
    RoomNotInLobbyError,
    RoomNotOnBoardError,
    RoundNotActiveError,
    TeamLimitExceededError,
    TeamNameTakenError,
    TeamNotFoundError,
    UnknownThemeError,
)
from app.models.player import Player, validate_nickname
from app.models.settings import GameSettings
from app.models.team import TEAM_COLOR_PALETTE, Team
from app.rooms.codes import generate_player_id, generate_token

if TYPE_CHECKING:
    from fastapi import WebSocket

log = logging.getLogger(__name__)

MAX_PLAYERS_PER_ROOM = 16
MAX_TEAMS = len(TEAM_COLOR_PALETTE)
TEAM_NAME_MAX = 24
MIN_PLAYERS_TO_START = 2

# How many themes each player may pick:
#   2 players in the room → up to 2 picks each (so 1–4 distinct themes total)
#   3+ players in the room → exactly 1 pick each (so ≥3 distinct themes total
#                            if everyone picks something different)
def _max_picks_per_player(player_count: int) -> int:
    return 2 if player_count == 2 else 1


# Interval between successive letter reveals during an active round.
LETTER_REVEAL_INTERVAL_SECONDS = 40.0

# AI theme generator caps.
MAX_GENERATED_THEMES_PER_ROOM = 5
THEME_GEN_COOLDOWN_SECONDS = 30.0

RoomState = Literal["lobby", "board", "round", "ended"]


def validate_team_name(raw: str) -> str:
    stripped = (raw or "").strip()
    if not (1 <= len(stripped) <= TEAM_NAME_MAX):
        raise ValueError("team_name_invalid")
    if any(ord(ch) < 0x20 for ch in stripped):
        raise ValueError("team_name_invalid")
    return stripped


class Room:
    """A single game room.

    Holds the roster, the per-player auth tokens, the live WebSocket
    connections, and (once the host starts the game) the board state,
    rotation, and current round.

    All state mutations should go through this class's methods, which acquire
    `self.lock` internally so callers don't have to.
    """

    def __init__(self, code: str, *, corpus: Corpus | None = None) -> None:
        self.code = code
        self.state: RoomState = "lobby"
        self.players: dict[str, Player] = {}
        self.host_id: str | None = None
        self.teams: dict[str, Team] = {}
        self.settings = GameSettings()
        self.corpus = corpus
        self.language = corpus.language if corpus else "en"

        # Game-in-progress state. Empty / None until `start_game` is called.
        self.board: Board | None = None
        self.current_round: Round | None = None
        self.rotation: list[str] = []
        self.rotation_index: int = 0
        self._used_word_ids: set[str] = set()
        self._round_counter: int = 0
        # Time-mode timer task, scheduled by the WS layer when a round starts
        # and cancelled by any termination path.
        self._round_end_task: asyncio.Task[None] | None = None
        # Letter-reveal task: uncovers one letter every 15 s during the round
        # so outsiders can guess along with the live description. Cancelled
        # whenever the round ends.
        self._letter_reveal_task: asyncio.Task[None] | None = None

        self._tokens: dict[str, str] = {}  # token -> player_id
        self._connections: dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

        # AI-generated themes for this room only. They augment self.corpus
        # without mutating it (the corpus is shared across all rooms).
        # Mapping is theme_id -> Theme; insertion order is preserved so the
        # picker UI shows them in the order they were generated.
        self.extra_themes: dict[str, Theme] = {}
        # Attribution: theme_id -> player_id who generated it.
        self.theme_generators: dict[str, str] = {}
        # Per-player cooldown timestamps for the AI theme generator
        # (player_id -> monotonic seconds at last successful generation).
        self._theme_gen_last_at: dict[str, float] = {}

    # ====================================================================== roster

    async def add_player(self, nickname: str) -> tuple[Player, str]:
        clean = validate_nickname(nickname)
        async with self.lock:
            if len(self.players) >= MAX_PLAYERS_PER_ROOM:
                raise RoomFullError()
            self._assert_nickname_free(clean)
            player_id = generate_player_id()
            token = generate_token()
            is_host = not self.players
            player = Player(id=player_id, nickname=clean, is_host=is_host)
            self.players[player_id] = player
            self._tokens[token] = player_id
            if is_host:
                self.host_id = player_id
            return player, token

    async def rename_player(self, player_id: str, new_nickname: str) -> Player:
        clean = validate_nickname(new_nickname)
        async with self.lock:
            player = self.players[player_id]
            if player.nickname == clean:
                return player
            self._assert_nickname_free(clean, except_player=player_id)
            player.nickname = clean
            return player

    async def remove_player(self, player_id: str) -> RemoveResult:
        """Hard-remove a player from the room.

        If the player was the current describer of an active round, the round
        is auto-ended (no scoring) and the describer rotation advances. The
        return value tells the caller what side-effects to broadcast.
        """
        async with self.lock:
            was_in_room = player_id in self.players
            self.players.pop(player_id, None)
            self._connections.pop(player_id, None)
            self._tokens = {t: pid for t, pid in self._tokens.items() if pid != player_id}

            if not was_in_room:
                return RemoveResult(
                    removed=False, host_changed=False, round_ended=None, game_ended=False
                )

            # Free the player from any team they were in.
            # (Membership is stored on Player, which is gone; nothing more to do.)

            host_changed = False
            if self.host_id == player_id:
                self.host_id = self._next_host_candidate()
                if self.host_id is not None:
                    self.players[self.host_id].is_host = True
                host_changed = True

            round_ended: Round | None = None
            game_ended = False
            if (
                self.state == "round"
                and self.current_round is not None
                and self.current_round.describer_id == player_id
            ):
                round_ended = self._finalize_round_locked(conceded=False, forced=True)
                game_ended = self.state == "ended"

            return RemoveResult(
                removed=True,
                host_changed=host_changed,
                round_ended=round_ended,
                game_ended=game_ended,
            )

    def _assert_nickname_free(self, nickname: str, except_player: str | None = None) -> None:
        lowered = nickname.casefold()
        for pid, p in self.players.items():
            if pid == except_player:
                continue
            if p.nickname.casefold() == lowered:
                raise NicknameTakenError()

    def _next_host_candidate(self) -> str | None:
        connected = [pid for pid, p in self.players.items() if p.is_connected]
        if connected:
            return connected[0]
        if self.players:
            return next(iter(self.players))
        return None

    # ====================================================================== teams

    async def create_team(self, name: str) -> Team:
        clean = validate_team_name(name)
        async with self.lock:
            if len(self.teams) >= MAX_TEAMS:
                raise TeamLimitExceededError()
            self._assert_team_name_free(clean)
            team = Team(
                id=secrets.token_urlsafe(6),
                name=clean,
                color=self._next_color(),
            )
            self.teams[team.id] = team
            return team

    async def delete_team(self, team_id: str) -> None:
        async with self.lock:
            if team_id not in self.teams:
                raise TeamNotFoundError()
            del self.teams[team_id]
            for p in self.players.values():
                if p.team_id == team_id:
                    p.team_id = None

    async def rename_team(self, team_id: str, new_name: str) -> Team:
        clean = validate_team_name(new_name)
        async with self.lock:
            team = self.teams.get(team_id)
            if team is None:
                raise TeamNotFoundError()
            if team.name == clean:
                return team
            self._assert_team_name_free(clean, except_team=team_id)
            team.name = clean
            return team

    async def set_player_theme_picks(
        self, player_id: str, theme_ids: list[str]
    ) -> Player:
        """Record this player's theme picks for the upcoming game.

        Enforces:
          * theme ids must exist in the room's corpus
          * count must be within the per-player cap (2 if room has 2 players,
            1 otherwise)
          * each theme is exclusive: a theme already picked by another player
            cannot be picked again (hard lock — server is the source of truth
            in case two clients race to the same chip).
        Picks are stored deduplicated, preserving the order the player chose.
        """
        if not isinstance(theme_ids, list) or not all(
            isinstance(t, str) for t in theme_ids
        ):
            raise ValueError("invalid_payload")
        async with self.lock:
            if self.state != "lobby":
                raise RoomNotInLobbyError()
            player = self.players.get(player_id)
            if player is None:
                raise InvalidTokenError()
            if self.corpus is None:
                raise BadThemePicksError()
            corpus_ids = self._all_theme_ids_locked()
            for tid in theme_ids:
                if tid not in corpus_ids:
                    raise BadThemePicksError()
            unique: list[str] = []
            seen: set[str] = set()
            for tid in theme_ids:
                if tid not in seen:
                    seen.add(tid)
                    unique.append(tid)
            max_picks = _max_picks_per_player(len(self.players))
            if len(unique) > max_picks:
                raise BadThemePicksError()
            # Exclusivity check: no two players may claim the same theme.
            for other in self.players.values():
                if other.id == player_id:
                    continue
                for tid in unique:
                    if tid in other.theme_picks:
                        raise BadThemePicksError()
            player.theme_picks = unique
            return player

    # =============================================================== themes (read)

    def _all_themes_locked(self) -> list[Theme]:
        """All themes a room can pick from: the shared corpus + per-room
        AI-generated additions. Used everywhere the old code read
        ``self.corpus.themes`` directly.
        """
        base = list(self.corpus.themes) if self.corpus is not None else []
        return base + list(self.extra_themes.values())

    def _all_theme_ids_locked(self) -> set[str]:
        ids = {t.id for t in self.corpus.themes} if self.corpus is not None else set()
        ids.update(self.extra_themes.keys())
        return ids

    # ====================================================== theme generation (AI)

    def add_generated_theme(self, theme: Theme, generator_player_id: str) -> None:
        """Append an AI-generated theme to this room only. The caller is
        responsible for cap / cooldown enforcement and for holding the
        room lock — see ``ws.router._handle_theme_generate``."""
        self.extra_themes[theme.id] = theme
        self.theme_generators[theme.id] = generator_player_id
        loop = asyncio.get_event_loop()
        self._theme_gen_last_at[generator_player_id] = loop.time()

    def can_generate_theme_locked(self, player_id: str) -> tuple[bool, str | None]:
        """Predicate for whether the player can generate right now. Returns
        ``(allowed, error_code)``. Caller must hold ``self.lock``.
        """
        if self.state != "lobby":
            return False, "room_not_in_lobby"
        if len(self.extra_themes) >= MAX_GENERATED_THEMES_PER_ROOM:
            return False, "theme_gen_cap_reached"
        last = self._theme_gen_last_at.get(player_id)
        if last is not None:
            loop = asyncio.get_event_loop()
            elapsed = loop.time() - last
            if elapsed < THEME_GEN_COOLDOWN_SECONDS:
                return False, "theme_gen_rate_limited"
        return True, None

    async def set_player_team(self, player_id: str, team_id: str | None) -> Player:
        async with self.lock:
            player = self.players.get(player_id)
            if player is None:
                raise InvalidTokenError()
            if team_id is not None and team_id not in self.teams:
                raise TeamNotFoundError()
            player.team_id = team_id
            return player

    async def randomize_teams(self, team_count: int) -> list[Team]:
        if team_count < 1 or team_count > MAX_TEAMS:
            raise TeamLimitExceededError()
        async with self.lock:
            for p in self.players.values():
                p.team_id = None
            self.teams.clear()
            new_teams: list[Team] = []
            for i in range(team_count):
                team = Team(
                    id=secrets.token_urlsafe(6),
                    name=f"Team {i + 1}",
                    color=TEAM_COLOR_PALETTE[i],
                )
                self.teams[team.id] = team
                new_teams.append(team)
            player_ids = list(self.players.keys())
            random.shuffle(player_ids)
            for idx, pid in enumerate(player_ids):
                self.players[pid].team_id = new_teams[idx % team_count].id
            return new_teams

    def _assert_team_name_free(self, name: str, except_team: str | None = None) -> None:
        lowered = name.casefold()
        for tid, t in self.teams.items():
            if tid == except_team:
                continue
            if t.name.casefold() == lowered:
                raise TeamNameTakenError()

    def _next_color(self) -> str:
        used = {t.color for t in self.teams.values()}
        for c in TEAM_COLOR_PALETTE:
            if c not in used:
                return c
        return TEAM_COLOR_PALETTE[0]

    # =================================================================== settings

    async def update_settings(self, patch: dict[str, Any]) -> GameSettings:
        async with self.lock:
            merged = self.settings.model_dump()
            merged.update({k: v for k, v in patch.items() if k in merged})
            try:
                self.settings = GameSettings.model_validate(merged)
            except Exception as e:
                raise ValueError("bad_settings") from e
            return self.settings

    # ============================================================ game state machine

    async def start_game(self) -> None:
        """Validate config, build teams (in solo) / rotation / board, transition to board."""
        async with self.lock:
            if self.state != "lobby":
                raise RoomNotInLobbyError()
            if len(self.players) < MIN_PLAYERS_TO_START:
                raise NotEnoughPlayersError()
            if self.corpus is None:
                raise BadTeamConfigError("corpus_missing")

            if self.settings.team_mode == "solo":
                self._init_solo_teams_locked()
            else:
                self._validate_teams_config_locked()

            # Validate per-player theme picks.
            self._validate_theme_picks_locked()

            # Reset scores at the start of every fresh game.
            for team in self.teams.values():
                team.score = 0

            # Build rotation from teams in their insertion order.
            teams_in_order = [
                [pid for pid in self.players if self.players[pid].team_id == t.id]
                for t in self.teams.values()
            ]
            self.rotation = compute_rotation(teams_in_order)
            self.rotation_index = 0
            self._used_word_ids = set()
            self._round_counter = 0

            # The board's themes are the *union* of every player's picks,
            # in corpus order. So a room with 3 players each picking a
            # different theme yields a 3-row board; if they all pick the
            # same theme, the board has just one row.
            picked_ids: set[str] = set()
            for p in self.players.values():
                picked_ids.update(p.theme_picks)
            selected_themes = [
                {"id": t.id, "name": t.name, "icon": t.icon}
                for t in self._all_themes_locked()
                if t.id in picked_ids
            ]
            self.board = Board(themes=selected_themes)
            self.current_round = None
            self.state = "board"

    def _validate_theme_picks_locked(self) -> None:
        assert self.corpus is not None
        corpus_ids = self._all_theme_ids_locked()
        max_picks = _max_picks_per_player(len(self.players))
        for player in self.players.values():
            picks = player.theme_picks
            if not picks or len(picks) > max_picks:
                raise BadThemePicksError()
            for tid in picks:
                if tid not in corpus_ids:
                    raise BadThemePicksError()

    def _init_solo_teams_locked(self) -> None:
        """Clear existing teams and create a 1-person team per player."""
        for p in self.players.values():
            p.team_id = None
        self.teams.clear()
        for i, player in enumerate(self.players.values()):
            team = Team(
                id=secrets.token_urlsafe(6),
                name=player.nickname,
                color=TEAM_COLOR_PALETTE[i % len(TEAM_COLOR_PALETTE)],
            )
            self.teams[team.id] = team
            player.team_id = team.id

    def _validate_teams_config_locked(self) -> None:
        if len(self.teams) < 2:
            raise BadTeamConfigError()
        for team in self.teams.values():
            if not any(p.team_id == team.id for p in self.players.values()):
                raise BadTeamConfigError()
        for p in self.players.values():
            if p.team_id is None:
                raise BadTeamConfigError()

    async def pick_cell(self, player_id: str, theme_id: str, difficulty: int) -> Round:
        async with self.lock:
            if self.state != "board" or self.board is None:
                raise RoomNotOnBoardError()
            if player_id != self._current_describer_id_locked():
                raise NotDescriberError()
            if not self.board.has_cell(theme_id, difficulty):
                raise UnknownThemeError()
            if self.board.is_used(theme_id, difficulty):
                raise CellAlreadyUsedError()
            if self.corpus is None:
                raise NoWordsAvailableError()

            word = pick_word_for_cell(
                self.corpus,
                theme_id,
                difficulty,
                exclude_ids=self._used_word_ids,
                extra_themes=self.extra_themes.values(),
            )
            if word is None:
                raise NoWordsAvailableError()

            ends_at: datetime | None = None
            if self.settings.mode == "time" and self.settings.time_seconds is not None:
                ends_at = datetime.now(UTC) + timedelta(seconds=self.settings.time_seconds)

            self._round_counter += 1
            self.current_round = Round(
                id=f"r-{self._round_counter}-{secrets.token_urlsafe(4)}",
                describer_id=player_id,
                theme_id=theme_id,
                difficulty=difficulty,
                base_score=self.board.base_score_for(difficulty),
                word_id=word.id,
                word_text=word.text,
                hint=word.hint,
                aliases=list(word.aliases),
                ends_at=ends_at,
            )
            self.board.mark_used(theme_id, difficulty)
            self._used_word_ids.add(word.id)
            self.state = "round"
            return self.current_round

    async def concede(self, player_id: str) -> Round:
        async with self.lock:
            if self.state != "round" or self.current_round is None:
                raise RoundNotActiveError()
            if player_id != self.current_round.describer_id:
                raise NotDescriberError()
            return self._finalize_round_locked(conceded=True, forced=False)

    async def force_end_round(self) -> Round:
        async with self.lock:
            if self.state != "round" or self.current_round is None:
                raise RoundNotActiveError()
            return self._finalize_round_locked(conceded=False, forced=True)

    async def play_again(self) -> None:
        """Send the room back to the lobby so players can re-pick themes
        before the next game. Scores reset, picks reset, but team
        composition and any AI-generated themes from the previous game
        carry over so players don't have to re-do setup.
        """
        async with self.lock:
            if self.state != "ended":
                raise RoomNotInLobbyError()
            for team in self.teams.values():
                team.score = 0
            for player in self.players.values():
                player.theme_picks = []
            self.board = None
            self.current_round = None
            self.rotation = []
            self.rotation_index = 0
            self._used_word_ids = set()
            self._round_counter = 0
            self.state = "lobby"

    # ---------------------------------------------------------- guess + text

    async def toggle_reaction(self, player_id: str, kind: str) -> dict[str, list[str]]:
        """Toggle a like/dislike from `player_id`. Returns the new aggregate state.

        Rules:
          - Same kind clicked again → reaction removed.
          - Different kind clicked → existing reaction replaced.
          - First time → reaction added.
          - The current describer is allowed to react too (no-op semantically;
            the frontend hides the buttons for them).
        """
        if kind not in ("like", "dislike"):
            raise ValueError("invalid_payload")
        async with self.lock:
            if self.state != "round" or self.current_round is None:
                raise RoundNotActiveError()
            if player_id not in self.players:
                raise InvalidTokenError()
            current = self.current_round.reactions.get(player_id)
            if current == kind:
                self.current_round.reactions.pop(player_id, None)
            else:
                self.current_round.reactions[player_id] = kind
            return self._reactions_state_locked()

    def _reactions_state_locked(self) -> dict[str, list[str]]:
        if self.current_round is None:
            return {"likes": [], "dislikes": []}
        likes = [pid for pid, k in self.current_round.reactions.items() if k == "like"]
        dislikes = [pid for pid, k in self.current_round.reactions.items() if k == "dislike"]
        return {"likes": likes, "dislikes": dislikes}

    async def set_describer_text(self, player_id: str, text: str) -> str:
        """Update the live-typed describer text and broadcast to non-describers.

        Returns the (possibly truncated) text actually stored.
        """
        if not isinstance(text, str):
            raise ValueError("invalid_payload")
        # Cap to a sane upper bound regardless of client behaviour.
        if len(text) > 2000:
            text = text[:2000]
        async with self.lock:
            if self.state != "round" or self.current_round is None:
                raise RoundNotActiveError()
            if player_id != self.current_round.describer_id:
                raise NotDescriberError()
            self.current_round.live_text = text
        await self.broadcast(
            {"type": "describer/text", "data": {"text": text}},
            exclude={player_id},
        )
        return text

    async def submit_guess(self, player_id: str, raw_text: str) -> GuessResult:
        async with self.lock:
            if self.state != "round" or self.current_round is None:
                raise RoundNotActiveError()
            round_obj = self.current_round
            if player_id == round_obj.describer_id:
                raise DescriberCannotGuessError()
            player = self.players.get(player_id)
            if player is None:
                raise InvalidTokenError()
            team_id = player.team_id
            if team_id is None or team_id not in self.teams:
                raise BadTeamConfigError()
            if player_id in round_obj.correct_player_ids:
                raise AlreadyGuessedCorrectlyError()

            guess_n = normalise(raw_text)
            if not guess_n:
                # Whitespace-only guess: ignored entirely; no attempt charged.
                return GuessResult(empty=True, team_id=team_id)

            # ---- attempt accounting ----
            penalty_applied = 0
            if self.settings.mode == "attempts":
                free_used = round_obj.attempts_used.get(player_id, 0)
                free_budget = self.settings.attempts_per_round
                if free_used < free_budget:
                    round_obj.attempts_used[player_id] = free_used + 1
                else:
                    paid_before = round_obj.paid_attempts.get(player_id, 0)
                    round_obj.paid_attempts[player_id] = paid_before + 1
                    penalty_applied = self.settings.scoring.penalty_per_attempt
                    self.teams[team_id].score -= penalty_applied
            else:
                # Time mode: count attempts for stats only; no penalty.
                round_obj.attempts_used[player_id] = round_obj.attempts_used.get(player_id, 0) + 1

            # ---- correctness ----
            is_correct = round_obj.matches(guess_n)
            team_position: int | None = None
            team_points = 0
            round_ended: Round | None = None

            if is_correct:
                round_obj.correct_player_ids.add(player_id)
                team_already_scored = any(
                    e.team_id == team_id for e in round_obj.correct_teams_order
                )
                if not team_already_scored:
                    position = len(round_obj.correct_teams_order) + 1
                    team_points = points_for_team_position(
                        round_obj.base_score,
                        position,
                        self.settings.scoring.decay,
                    )
                    self.teams[team_id].score += team_points
                    round_obj.correct_teams_order.append(
                        CorrectTeamEntry(
                            team_id=team_id,
                            player_id=player_id,
                            position=position,
                            points=team_points,
                            at=datetime.now(UTC),
                        )
                    )
                    team_position = position

                # Round only ends naturally once every non-describer
                # *player* has guessed the word — not just one per team.
                # This keeps everyone engaged until the last person gets it.
                if self._all_non_describer_players_guessed_locked():
                    round_ended = self._finalize_round_locked(conceded=False, forced=False)

            free_left: int | None = None
            if self.settings.mode == "attempts":
                free_left = max(
                    0,
                    self.settings.attempts_per_round - round_obj.attempts_used.get(player_id, 0),
                )
            paid_total = round_obj.paid_attempts.get(player_id, 0)
            new_team_score = self.teams[team_id].score

            return GuessResult(
                empty=False,
                correct=is_correct,
                team_id=team_id,
                team_position=team_position,
                team_points=team_points,
                penalty_applied=penalty_applied,
                new_team_score=new_team_score,
                free_attempts_left=free_left,
                paid_attempts_total=paid_total,
                round_ended=round_ended,
            )

    def _all_non_describer_teams_scored_locked(self) -> bool:
        if self.current_round is None:
            return False
        describer = self.players.get(self.current_round.describer_id)
        if describer is None:
            # describer left; treat as "everyone has scored that can"
            return True
        describer_team_id = describer.team_id
        non_describer_team_ids = [t.id for t in self.teams.values() if t.id != describer_team_id]
        if not non_describer_team_ids:
            return False
        scored = {e.team_id for e in self.current_round.correct_teams_order}
        return all(tid in scored for tid in non_describer_team_ids)

    def _all_non_describer_players_guessed_locked(self) -> bool:
        """True once every non-describer player has guessed correctly.

        This is the stronger end-condition the game uses: a round won't
        end until the *last* player has gotten it, so nobody is left
        twiddling their thumbs after their team-mate scores.
        """
        if self.current_round is None:
            return False
        describer_id = self.current_round.describer_id
        non_describer_ids = [pid for pid in self.players if pid != describer_id]
        if not non_describer_ids:
            return False
        correct = self.current_round.correct_player_ids
        return all(pid in correct for pid in non_describer_ids)

    # ----------------------------------------------- finalising a round

    def _finalize_round_locked(self, *, conceded: bool, forced: bool) -> Round:
        """End the current round, compute scoring, attach results. Caller
        must hold self.lock."""
        assert self.current_round is not None
        ended = self.current_round
        ended.state = "ended"

        # Determine the describer's team (if any) so we can both exclude it
        # from `k` and credit it with the reward.
        describer_player = self.players.get(ended.describer_id)
        describer_team_id = describer_player.team_id if describer_player else None

        # Count non-describer teams that scored.
        correct_non_describer_count = sum(
            1 for e in ended.correct_teams_order if e.team_id != describer_team_id
        )
        reward = describer_reward(
            ended.base_score,
            correct_non_describer_team_count=correct_non_describer_count,
            base_pct=self.settings.scoring.describer_base_pct,
            bonus_pct=self.settings.scoring.describer_bonus_pct,
            conceded=conceded,
        )
        if describer_team_id and reward > 0 and describer_team_id in self.teams:
            self.teams[describer_team_id].score += reward
        ended.describer_points = reward

        # Build the results dict (used by round/ended.results).
        per_team: list[dict[str, object]] = []
        scored_team_ids = {e.team_id for e in ended.correct_teams_order}
        # Add a row per existing team — winners + everyone else.
        for team in self.teams.values():
            entry = next(
                (e for e in ended.correct_teams_order if e.team_id == team.id),
                None,
            )
            per_team.append(
                {
                    "team_id": team.id,
                    "first_player_id": entry.player_id if entry else None,
                    "correct_at": entry.at.isoformat() if entry else None,
                    "position": entry.position if entry else None,
                    "points": entry.points if entry else 0,
                    "new_score": team.score,
                }
            )

        per_player_attempts: list[dict[str, object]] = []
        all_attempt_player_ids = set(ended.attempts_used) | set(ended.paid_attempts)
        for pid in all_attempt_player_ids:
            free_used = ended.attempts_used.get(pid, 0)
            paid_used = ended.paid_attempts.get(pid, 0)
            per_player_attempts.append(
                {
                    "player_id": pid,
                    "free_used": free_used,
                    "paid_used": paid_used,
                    "penalty_total": paid_used * self.settings.scoring.penalty_per_attempt,
                }
            )

        ended.results = {
            "describer_id": ended.describer_id,
            "describer_points": reward,
            "describer_team_id": describer_team_id,
            "correct_non_describer_team_count": correct_non_describer_count,
            "scored_team_ids": list(scored_team_ids),
            "per_team": per_team,
            "per_player_attempts": per_player_attempts,
        }

        # Cancel any round-scoped background tasks — the time-mode end-of-round
        # timer and the letter-reveal task. Skip cancelling ourselves: when one
        # of these tasks is the one calling this method, cancelling its own
        # ref would raise CancelledError on the next await (lock release) and
        # abort the broadcast.
        current = asyncio.current_task()
        for attr in ("_round_end_task", "_letter_reveal_task"):
            task = getattr(self, attr, None)
            if task is not None and task is not current and not task.done():
                task.cancel()
            setattr(self, attr, None)

        # Advance the state machine.
        self._advance_describer_locked()
        if self.board is not None and self.board.is_full():
            self.state = "ended"
        else:
            self.state = "board"
        self.current_round = None
        return ended

    # ------------------------------------------------------------ describer rotation

    @property
    def current_describer_id(self) -> str | None:
        if not self.rotation:
            return None
        return self._current_describer_id_locked()

    def _current_describer_id_locked(self) -> str | None:
        if not self.rotation:
            return None
        n = len(self.rotation)
        # Skip past any rotation entries whose player has left.
        for offset in range(n):
            candidate = self.rotation[(self.rotation_index + offset) % n]
            if candidate in self.players:
                # Park rotation_index here so subsequent reads are stable.
                self.rotation_index = (self.rotation_index + offset) % n
                return candidate
        return None

    def _advance_describer_locked(self) -> None:
        if not self.rotation:
            return
        n = len(self.rotation)
        for _ in range(n):
            self.rotation_index = (self.rotation_index + 1) % n
            if self.rotation[self.rotation_index] in self.players:
                return
        # Everyone's gone. Leave rotation_index where it is.

    # ====================================================================== tokens

    def player_id_for_token(self, token: str) -> str | None:
        return self._tokens.get(token)

    # ================================================================= connections

    async def attach_connection(self, player_id: str, ws: WebSocket) -> None:
        old: WebSocket | None = None
        async with self.lock:
            if player_id not in self.players:
                raise InvalidTokenError()
            old = self._connections.get(player_id)
            self._connections[player_id] = ws
            self.players[player_id].is_connected = True
        if old is not None:
            try:
                await old.close(code=4000, reason="replaced")
            except Exception:
                pass

    async def detach_connection(self, player_id: str, ws: WebSocket) -> bool:
        async with self.lock:
            current = self._connections.get(player_id)
            if current is not ws:
                return False
            self._connections.pop(player_id, None)
            if player_id in self.players:
                self.players[player_id].is_connected = False
            return True

    def is_empty(self) -> bool:
        return not self.players

    def connection_count(self) -> int:
        return len(self._connections)

    # ================================================================== broadcasts

    async def broadcast(
        self,
        event: dict[str, object],
        *,
        exclude: set[str] | None = None,
    ) -> None:
        exclude = exclude or set()
        targets = [(pid, ws) for pid, ws in self._connections.items() if pid not in exclude]
        await asyncio.gather(*(_safe_send(ws, event) for _, ws in targets), return_exceptions=True)

    async def send_to(self, player_id: str, event: dict[str, object]) -> None:
        ws = self._connections.get(player_id)
        if ws is None:
            return
        await _safe_send(ws, event)

    # ================================================================== snapshot

    def snapshot(self) -> dict[str, object]:
        """Per-room state that's identical for every recipient."""
        snap: dict[str, object] = {
            "code": self.code,
            "state": self.state,
            "host_id": self.host_id,
            "language": self.language,
            "players": [p.public() for p in self.players.values()],
            "teams": self._teams_public(),
            "settings": self.settings.model_dump(),
            "max_theme_picks_per_player": _max_picks_per_player(len(self.players)),
        }
        if self.corpus is not None:
            snap["corpus_themes"] = [
                {
                    "id": t.id,
                    "name": t.name,
                    "icon": t.icon,
                    "generated_by": self.theme_generators.get(t.id),
                }
                for t in self._all_themes_locked()
            ]
        if self.board is not None:
            snap["board"] = self.board.public()
        if self.current_round is not None:
            snap["current_round"] = self.current_round.public()
        if self.rotation:
            snap["current_describer_id"] = self.current_describer_id
            snap["describer_queue"] = list(self.rotation)
            snap["rotation_index"] = self.rotation_index
        return snap

    def private_round_info_for(self, player_id: str) -> dict[str, object] | None:
        """Return the describer-only word data, if `player_id` is the
        describer of the active round."""
        if self.current_round is None:
            return None
        if self.current_round.describer_id != player_id:
            return None
        if self.current_round.state != "active":
            return None
        return self.current_round.private()

    def private_round_state_for(self, player_id: str) -> dict[str, object] | None:
        """Return the player's per-round private state, for use in mid-round
        reconnect snapshots. Empty for the describer; carries the guesser's
        attempt budget so the UI counter survives a page refresh.
        """
        if self.current_round is None:
            return None
        if self.current_round.state != "active":
            return None
        round_obj = self.current_round
        free_used = round_obj.attempts_used.get(player_id, 0)
        paid_used = round_obj.paid_attempts.get(player_id, 0)
        free_attempts_left: int | None
        if self.settings.mode == "attempts":
            free_attempts_left = max(0, self.settings.attempts_per_round - free_used)
        else:
            free_attempts_left = None
        return {
            "free_attempts_left": free_attempts_left,
            "paid_attempts_total": paid_used,
            "you_have_guessed_correctly": player_id in round_obj.correct_player_ids,
        }

    def scoreboard(self) -> list[dict[str, object]]:
        return [
            {
                "team_id": t.id,
                "name": t.name,
                "color": t.color,
                "score": t.score,
            }
            for t in self.teams.values()
        ]

    def _teams_public(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for t in self.teams.values():
            members = [pid for pid, p in self.players.items() if p.team_id == t.id]
            out.append(t.public(members))
        return out

    def is_host(self, player_id: str) -> bool:
        return self.host_id == player_id


class RemoveResult:
    """What `Room.remove_player` did, so the caller can broadcast appropriately."""

    def __init__(
        self,
        *,
        removed: bool,
        host_changed: bool,
        round_ended: Round | None,
        game_ended: bool,
    ) -> None:
        self.removed = removed
        self.host_changed = host_changed
        self.round_ended = round_ended
        self.game_ended = game_ended


@dataclass
class GuessResult:
    """What submit_guess did. The caller (WS handler) decides what to broadcast."""

    empty: bool = False
    correct: bool = False
    team_id: str | None = None
    team_position: int | None = None  # 1-indexed; None if team already scored
    team_points: int = 0
    penalty_applied: int = 0
    new_team_score: int = 0
    free_attempts_left: int | None = None  # None in time mode
    paid_attempts_total: int = 0
    round_ended: Round | None = None  # set if this guess naturally ended the round


async def _safe_send(ws: WebSocket, event: dict[str, object]) -> None:
    try:
        await ws.send_json(event)
    except Exception as e:  # pragma: no cover - logged only
        log.debug("ws send failed: %r", e)


BroadcastFn = Callable[[dict[str, object]], Awaitable[None]]
