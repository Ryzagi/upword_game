from __future__ import annotations

from typing import Any

DEFAULT_BASE_VALUES: tuple[int, ...] = (100, 200, 300, 400, 500)


class Board:
    """The themes × difficulties matrix for a single game.

    Themes come from the room's corpus, carrying their localised display name
    + optional icon so the client doesn't need a separate corpus lookup.
    Cells get marked as used as the describer picks them; the board is full
    when every (theme, difficulty) pair has been used.
    """

    def __init__(
        self,
        themes: list[dict[str, Any]],
        base_values: tuple[int, ...] = DEFAULT_BASE_VALUES,
    ) -> None:
        # `themes` items must have at least an `id`; `name` and `icon` are
        # included verbatim in the public payload.
        self.themes: list[dict[str, Any]] = [dict(t) for t in themes]
        self.theme_ids: list[str] = [t["id"] for t in self.themes]
        self.base_values = tuple(base_values)
        self.used: list[tuple[str, int]] = []  # (theme_id, difficulty)

    @property
    def total_cells(self) -> int:
        return len(self.theme_ids) * len(self.base_values)

    def has_cell(self, theme_id: str, difficulty: int) -> bool:
        return theme_id in self.theme_ids and 1 <= difficulty <= len(self.base_values)

    def is_used(self, theme_id: str, difficulty: int) -> bool:
        return (theme_id, difficulty) in self.used

    def mark_used(self, theme_id: str, difficulty: int) -> None:
        if not self.is_used(theme_id, difficulty):
            self.used.append((theme_id, difficulty))

    def is_full(self) -> bool:
        return len(self.used) >= self.total_cells

    def base_score_for(self, difficulty: int) -> int:
        return self.base_values[difficulty - 1]

    def reset(self) -> None:
        self.used.clear()

    def public(self) -> dict[str, object]:
        return {
            "themes": list(self.themes),
            "base_values": list(self.base_values),
            "used": [{"theme_id": tid, "difficulty": d} for tid, d in self.used],
        }
