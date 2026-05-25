"""Scoring formulas for a round.

Per-team decay: when a team's first member guesses correctly, the team is
added to the correct-team queue at 1-indexed position `n`; the team is
credited with `floor(base_score * decay^(n-1))` points.

Describer reward: half of base_score if at least one non-describer team
guesses, plus a small bonus per *additional* non-describer team, capped at
base_score. Conceded rounds and rounds with no correct guess pay 0.
"""

from __future__ import annotations

import math


def points_for_team_position(base_score: int, position: int, decay: float) -> int:
    """Return the points the team coming in at 1-indexed `position` earns."""
    if position < 1 or base_score <= 0:
        return 0
    if decay <= 0:
        return base_score if position == 1 else 0
    return math.floor(base_score * (decay ** (position - 1)))


def describer_reward(
    base_score: int,
    *,
    correct_non_describer_team_count: int,
    base_pct: float = 0.5,
    bonus_pct: float = 0.1,
    conceded: bool = False,
) -> int:
    """Describer's reward for this round.

    `correct_non_describer_team_count` is `k` — the number of distinct teams
    *other than the describer's own* that have at least one correct guess.
    The describer's own team's correct guesses (other members) do NOT count
    toward `k`, even though those guesses still earn the team decay points.
    """
    if conceded or correct_non_describer_team_count <= 0 or base_score <= 0:
        return 0
    reward = math.floor(base_score * base_pct) + math.floor(base_score * bonus_pct) * (
        correct_non_describer_team_count - 1
    )
    return min(reward, base_score)
