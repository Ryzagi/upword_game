"""Describer rotation: round-robin team-then-player.

Given teams `A=[a1,a2]`, `B=[b1]`, `C=[c1,c2,c3]` (in that order), the rotation is:

    a1, b1, c1,   a2, c2,   c3,   then repeat from a1.

That is: cycle teams; within each team, take the player at the current cycle
index; if that team has been exhausted for this cycle, skip it. Once every
team has been exhausted, the cycle resets and we start over.
"""

from __future__ import annotations


def compute_rotation(teams_in_order: list[list[str]]) -> list[str]:
    """Compute a full-rotation order across all players.

    `teams_in_order` is a list of teams; each team is a list of player IDs.
    Returns a single flat list containing every player exactly once, ordered
    by the round-robin rule described in the module docstring. Empty teams
    are skipped silently.
    """
    if not teams_in_order:
        return []
    max_size = max((len(team) for team in teams_in_order), default=0)
    rotation: list[str] = []
    for cycle in range(max_size):
        for team in teams_in_order:
            if cycle < len(team):
                rotation.append(team[cycle])
    return rotation
