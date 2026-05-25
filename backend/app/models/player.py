from pydantic import BaseModel


class Player(BaseModel):
    """A connected (or recently-disconnected) player in a room."""

    id: str
    nickname: str
    is_host: bool = False
    is_connected: bool = False
    team_id: str | None = None
    # Themes this player has picked for the upcoming game. The board built at
    # start_game uses the union of every player's picks. Per-player cap:
    #   2-player room → up to 2 picks
    #   3+ player room → exactly 1 pick
    theme_picks: list[str] = []

    def public(self) -> dict[str, object]:
        """Serialise the fields that clients are allowed to see."""
        return {
            "id": self.id,
            "nickname": self.nickname,
            "is_host": self.is_host,
            "is_connected": self.is_connected,
            "team_id": self.team_id,
            "theme_picks": list(self.theme_picks),
        }


NICKNAME_MIN_LEN = 1
NICKNAME_MAX_LEN = 24


def validate_nickname(raw: str) -> str:
    """Strip and validate a nickname, returning the canonical form.

    Raises ValueError with a stable error code on rejection.
    """
    stripped = (raw or "").strip()
    if not (NICKNAME_MIN_LEN <= len(stripped) <= NICKNAME_MAX_LEN):
        raise ValueError("nickname_invalid")
    if any(ch.isspace() and ch != " " for ch in stripped):
        raise ValueError("nickname_invalid")
    if any(ord(ch) < 0x20 for ch in stripped):
        raise ValueError("nickname_invalid")
    return stripped
