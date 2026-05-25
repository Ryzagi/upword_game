import pytest

from app.models.errors import NicknameTakenError, RoomFullError, RoomNotFoundError
from app.rooms.codes import (
    ROOM_CODE_ALPHABET,
    ROOM_CODE_LENGTH,
    generate_player_id,
    generate_room_code,
    generate_token,
)
from app.rooms.manager import RoomManager
from app.rooms.room import MAX_PLAYERS_PER_ROOM, Room


def test_room_code_shape() -> None:
    for _ in range(50):
        code = generate_room_code()
        assert len(code) == ROOM_CODE_LENGTH
        assert all(ch in ROOM_CODE_ALPHABET for ch in code)
        for forbidden in ("I", "L", "O", "0", "1"):
            assert forbidden not in code


def test_player_id_and_token_are_unique() -> None:
    ids = {generate_player_id() for _ in range(100)}
    tokens = {generate_token() for _ in range(100)}
    assert len(ids) == 100
    assert len(tokens) == 100


async def test_room_add_first_player_becomes_host() -> None:
    room = Room("AAA111")
    player, token = await room.add_player("Alex")
    assert player.is_host is True
    assert room.host_id == player.id
    assert room.player_id_for_token(token) == player.id


async def test_room_add_second_player_is_not_host() -> None:
    room = Room("AAA111")
    await room.add_player("Alex")
    player2, _ = await room.add_player("Mira")
    assert player2.is_host is False


async def test_room_rejects_duplicate_nickname_case_insensitive() -> None:
    room = Room("AAA111")
    await room.add_player("Alex")
    with pytest.raises(NicknameTakenError):
        await room.add_player("alex")
    with pytest.raises(NicknameTakenError):
        await room.add_player("ALEX  ")


async def test_room_rejects_when_full() -> None:
    room = Room("AAA111")
    for i in range(MAX_PLAYERS_PER_ROOM):
        await room.add_player(f"P{i}")
    with pytest.raises(RoomFullError):
        await room.add_player("Overflow")


async def test_remove_host_passes_torch() -> None:
    room = Room("AAA111")
    host, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    await room.remove_player(host.id)
    assert room.host_id == p2.id
    assert room.players[p2.id].is_host is True


async def test_rename_player_validates_uniqueness() -> None:
    room = Room("AAA111")
    p1, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    # rename to taken name
    with pytest.raises(NicknameTakenError):
        await room.rename_player(p2.id, "Alex")
    # rename to a different case of one's own name is allowed (no clash with others)
    same = await room.rename_player(p1.id, "alex")
    assert same.nickname == "alex"


async def test_rename_invalid_nickname_raises_value_error() -> None:
    room = Room("AAA111")
    p, _ = await room.add_player("Alex")
    with pytest.raises(ValueError):
        await room.rename_player(p.id, "   ")
    with pytest.raises(ValueError):
        await room.rename_player(p.id, "x" * 100)


# --------------------------------------------------------------- RoomManager


async def test_manager_creates_unique_codes(corpora) -> None:  # type: ignore[no-untyped-def]
    mgr = RoomManager(corpora=corpora)
    seen = set()
    for _ in range(20):
        room, _, _ = await mgr.create_room("Host")
        assert room.code not in seen
        seen.add(room.code)


async def test_manager_join_uses_existing_room(corpora) -> None:  # type: ignore[no-untyped-def]
    mgr = RoomManager(corpora=corpora)
    room, host, _ = await mgr.create_room("Alex")
    same_room, joiner, _ = await mgr.join_room(room.code, "Mira")
    assert same_room is room
    assert host.id != joiner.id


async def test_manager_join_unknown_room_raises(corpora) -> None:  # type: ignore[no-untyped-def]
    mgr = RoomManager(corpora=corpora)
    with pytest.raises(RoomNotFoundError):
        await mgr.join_room("ZZZZZZ", "Mira")


async def test_manager_drops_empty_room(corpora) -> None:  # type: ignore[no-untyped-def]
    mgr = RoomManager(corpora=corpora)
    room, host, _ = await mgr.create_room("Alex")
    await room.remove_player(host.id)
    assert await mgr.drop_room_if_empty(room.code) is True
    assert mgr.get_room(room.code) is None
