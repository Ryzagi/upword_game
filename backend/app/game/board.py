from __future__ import annotations

import random as _random
from typing import Any

DEFAULT_BASE_VALUES: tuple[int, ...] = (100, 200, 300, 400, 500)

# Lightning (bonus) cells pay a score multiplier and are shown to everyone
# before the cell is picked, so the describer can strategically aim for them.
LIGHTNING_MULTIPLIERS: tuple[float, ...] = (1.5, 2.0)
# Roughly one lightning cell per this many cells, capped so big boards don't
# turn into a fireworks show.
LIGHTNING_CELL_DENSITY = 8
LIGHTNING_MAX_CELLS = 4


class Board:
    """The themes × difficulties matrix for a single game.

    Themes come from the room's corpus, carrying their localised display name
    + optional icon so the client doesn't need a separate corpus lookup.
    Cells get marked as used as the describer picks them; the board is full
    when every (theme, difficulty) pair has been used.

    A handful of cells may be flagged as "lightning" — they pay a score
    multiplier (e.g. ×1.5 / ×2). The multipliers are visible up front so
    picking a lightning cell is a deliberate, high-risk/high-reward choice.
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
        # (theme_id, difficulty) -> multiplier. Empty by default; populated
        # by assign_lightning().
        self.lightning: dict[tuple[str, int], float] = {}

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

    def multiplier_for(self, theme_id: str, difficulty: int) -> float:
        """Score multiplier for a cell — 1.0 for a normal cell."""
        return self.lightning.get((theme_id, difficulty), 1.0)

    def assign_lightning(self, rng: _random.Random | None = None) -> None:
        """Randomly designate a few cells as lightning (bonus) cells.

        Idempotent-ish: clears any previous assignment first, so it's safe
        to call on a fresh board. Count scales with board size and is capped.
        """
        self.lightning = {}
        all_cells = [
            (tid, d)
            for tid in self.theme_ids
            for d in range(1, len(self.base_values) + 1)
        ]
        if not all_cells:
            return
        chooser = rng or _random
        count = max(1, len(all_cells) // LIGHTNING_CELL_DENSITY)
        count = min(count, LIGHTNING_MAX_CELLS, len(all_cells))
        chosen = chooser.sample(all_cells, count)
        for cell in chosen:
            self.lightning[cell] = chooser.choice(LIGHTNING_MULTIPLIERS)

    def reset(self) -> None:
        self.used.clear()

    def public(self) -> dict[str, object]:
        return {
            "themes": list(self.themes),
            "base_values": list(self.base_values),
            "used": [{"theme_id": tid, "difficulty": d} for tid, d in self.used],
            "lightning": [
                {"theme_id": tid, "difficulty": d, "multiplier": mult}
                for (tid, d), mult in self.lightning.items()
            ],
        }
