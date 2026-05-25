import secrets

# 31 chars, no I / L / O / 0 / 1 — humans can read this off a screen.
ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6


def generate_room_code() -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def generate_player_id() -> str:
    return secrets.token_urlsafe(8)


def generate_token() -> str:
    return secrets.token_urlsafe(32)
