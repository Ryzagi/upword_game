from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.corpus.loader import normalise


@dataclass
class CorrectTeamEntry:
    """A team's first correct guess, in the order teams hit it."""

    team_id: str
    player_id: str
    position: int  # 1-indexed among correct teams
    points: int
    at: datetime


class Round:
    """A single round in progress (or just-ended).

    `word_text` / `hint` / `aliases` are server-private fields: only the
    describer's connection should ever receive them. The `public()`
    serialisation omits them; `private()` includes them.
    """

    def __init__(
        self,
        *,
        id: str,
        describer_id: str,
        theme_id: str,
        difficulty: int,
        base_score: int,
        word_id: str,
        word_text: str,
        hint: str,
        aliases: list[str] | None = None,
        ends_at: datetime | None,
    ) -> None:
        self.id = id
        self.describer_id = describer_id
        self.theme_id = theme_id
        self.difficulty = difficulty
        self.base_score = base_score
        # Lightning-cell multiplier already baked into base_score above;
        # kept around purely so the UI can show a "⚡ ×2" badge. 1.0 = normal.
        self.score_multiplier: float = 1.0
        self.word_id = word_id
        self.word_text = word_text
        self.hint = hint
        self.aliases: list[str] = list(aliases or [])
        self.started_at: datetime = datetime.now(UTC)
        self.ends_at: datetime | None = ends_at
        self.state: Literal["active", "ended"] = "active"

        # Phase 4 — running per-round state
        self.live_text: str = ""
        # player_id -> free attempts consumed this round
        self.attempts_used: dict[str, int] = {}
        # player_id -> paid attempts consumed this round
        self.paid_attempts: dict[str, int] = {}
        # ordered list of team-firsts (one entry per team)
        self.correct_teams_order: list[CorrectTeamEntry] = []
        # every player who has guessed correctly (used to block re-submissions)
        self.correct_player_ids: set[str] = set()
        # every player who has actively conceded this round — they gave up
        # trying to guess. Conceded players score nothing and are excluded
        # from the "everyone has finished" check that ends the round.
        self.conceded_player_ids: set[str] = set()
        # set when the round is finalised
        self.describer_points: int = 0
        # Populated by Room._finalize_round_locked; mirrors the round/ended
        # `results` payload so any later consumer can read the breakdown.
        self.results: dict[str, object] | None = None
        # player_id -> "like" | "dislike". Reset per round.
        self.reactions: dict[str, str] = {}
        # Indices into `word_text` that have been revealed to outsiders so
        # they can guess along with the live description. A reveal task
        # uncovers one un-revealed non-whitespace index every 15 s.
        self.revealed_indices: set[int] = set()
        # Pre-computed normalised target forms (word + aliases).
        self._normalised_targets: set[str] = {
            n for n in (normalise(s) for s in [word_text, *self.aliases]) if n
        }

    def letter_pattern(self) -> str:
        """Masked form of the word for non-describer eyes.

        Each non-whitespace char becomes `_` until its index appears in
        `revealed_indices`. Whitespace is left intact so multi-word targets
        keep their shape (e.g. "ice cream" -> "_c_ _r_a_").
        """
        parts: list[str] = []
        for i, ch in enumerate(self.word_text):
            if ch.isspace():
                parts.append(ch)
            elif i in self.revealed_indices:
                parts.append(ch)
            else:
                parts.append("_")
        return "".join(parts)

    def hidden_letter_indices(self) -> list[int]:
        return [
            i
            for i, ch in enumerate(self.word_text)
            if not ch.isspace() and i not in self.revealed_indices
        ]

    def matches(self, normalised_guess: str) -> bool:
        return normalised_guess in self._normalised_targets

    def public(self) -> dict[str, object]:
        """Fields safe to broadcast to everyone, including non-describers."""
        likes = [pid for pid, k in self.reactions.items() if k == "like"]
        dislikes = [pid for pid, k in self.reactions.items() if k == "dislike"]
        return {
            "id": self.id,
            "describer_id": self.describer_id,
            "theme_id": self.theme_id,
            "difficulty": self.difficulty,
            "base_score": self.base_score,
            "score_multiplier": self.score_multiplier,
            "started_at": self.started_at.isoformat(),
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "state": self.state,
            "live_text": self.live_text,
            "reactions": {"likes": likes, "dislikes": dislikes},
            "letter_pattern": self.letter_pattern(),
            "letter_count": sum(1 for ch in self.word_text if not ch.isspace()),
            "revealed_indices": sorted(self.revealed_indices),
            "conceded_player_ids": sorted(self.conceded_player_ids),
            "correct_player_ids": sorted(self.correct_player_ids),
        }

    def private(self) -> dict[str, object]:
        """Describer-only payload — word + hint."""
        return {
            "word_id": self.word_id,
            "word_text": self.word_text,
            "hint": self.hint,
        }
