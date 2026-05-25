from pydantic import BaseModel

# Eight visually distinct colours; the team manager hands them out in order.
TEAM_COLOR_PALETTE: tuple[str, ...] = (
    "#ef4444",  # red
    "#3b82f6",  # blue
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#14b8a6",  # teal
    "#64748b",  # slate
)


class Team(BaseModel):
    id: str
    name: str
    color: str
    score: int = 0

    def public(self, player_ids: list[str]) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "score": self.score,
            "player_ids": player_ids,
        }
