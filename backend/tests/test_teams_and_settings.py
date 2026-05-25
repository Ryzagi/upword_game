import pytest

from app.models.errors import (
    TeamLimitExceededError,
    TeamNameTakenError,
    TeamNotFoundError,
)
from app.models.team import TEAM_COLOR_PALETTE
from app.rooms.room import MAX_TEAMS, Room

# ----------------------------------------------------------- create / rename


async def test_create_team_picks_next_color() -> None:
    room = Room("AAA111")
    a = await room.create_team("Red")
    b = await room.create_team("Blue")
    assert a.color == TEAM_COLOR_PALETTE[0]
    assert b.color == TEAM_COLOR_PALETTE[1]
    assert {a.id, b.id} == set(room.teams.keys())


async def test_create_team_rejects_duplicate_name_case_insensitive() -> None:
    room = Room("AAA111")
    await room.create_team("Red")
    with pytest.raises(TeamNameTakenError):
        await room.create_team("RED")


async def test_create_team_rejects_when_full() -> None:
    room = Room("AAA111")
    for i in range(MAX_TEAMS):
        await room.create_team(f"T{i}")
    with pytest.raises(TeamLimitExceededError):
        await room.create_team("Overflow")


async def test_rename_team_validates_and_persists() -> None:
    room = Room("AAA111")
    t = await room.create_team("Red")
    renamed = await room.rename_team(t.id, "Crimson")
    assert renamed.name == "Crimson"
    assert room.teams[t.id].name == "Crimson"


async def test_rename_team_rejects_duplicate() -> None:
    room = Room("AAA111")
    await room.create_team("Red")
    blue = await room.create_team("Blue")
    with pytest.raises(TeamNameTakenError):
        await room.rename_team(blue.id, "red")


async def test_rename_team_unknown_raises() -> None:
    room = Room("AAA111")
    with pytest.raises(TeamNotFoundError):
        await room.rename_team("nope", "Whatever")


# ------------------------------------------------------------- assign / delete


async def test_set_player_team_links_and_unlinks() -> None:
    room = Room("AAA111")
    p, _ = await room.add_player("Alex")
    t = await room.create_team("Red")
    await room.set_player_team(p.id, t.id)
    assert room.players[p.id].team_id == t.id
    await room.set_player_team(p.id, None)
    assert room.players[p.id].team_id is None


async def test_set_player_team_rejects_unknown_team() -> None:
    room = Room("AAA111")
    p, _ = await room.add_player("Alex")
    with pytest.raises(TeamNotFoundError):
        await room.set_player_team(p.id, "ghost")


async def test_delete_team_releases_members() -> None:
    room = Room("AAA111")
    p, _ = await room.add_player("Alex")
    t = await room.create_team("Red")
    await room.set_player_team(p.id, t.id)
    await room.delete_team(t.id)
    assert t.id not in room.teams
    assert room.players[p.id].team_id is None


# ---------------------------------------------------------------- randomize


async def test_randomize_teams_distributes_players_evenly() -> None:
    room = Room("AAA111")
    for i in range(7):
        await room.add_player(f"P{i}")
    new_teams = await room.randomize_teams(3)
    assert len(new_teams) == 3
    counts = [sum(1 for p in room.players.values() if p.team_id == t.id) for t in new_teams]
    # 7 players over 3 teams: counts should be [3, 2, 2] in some order.
    assert sorted(counts) == [2, 2, 3]
    assert all(p.team_id is not None for p in room.players.values())


async def test_randomize_teams_rejects_too_many() -> None:
    room = Room("AAA111")
    with pytest.raises(TeamLimitExceededError):
        await room.randomize_teams(MAX_TEAMS + 1)
    with pytest.raises(TeamLimitExceededError):
        await room.randomize_teams(0)


# ------------------------------------------------------------------- settings


async def test_update_settings_merges_partial() -> None:
    room = Room("AAA111")
    s = await room.update_settings({"mode": "time", "time_seconds": 90})
    assert s.mode == "time"
    assert s.time_seconds == 90
    # Other fields preserved at defaults.
    assert s.attempts_per_round == 5


async def test_update_settings_rejects_invalid_time_value() -> None:
    room = Room("AAA111")
    with pytest.raises(ValueError, match="bad_settings"):
        await room.update_settings({"mode": "time", "time_seconds": 42})


async def test_update_settings_rejects_invalid_attempts() -> None:
    room = Room("AAA111")
    with pytest.raises(ValueError, match="bad_settings"):
        await room.update_settings({"mode": "attempts", "attempts_per_round": 0})


async def test_update_settings_allows_unlimited_time() -> None:
    room = Room("AAA111")
    s = await room.update_settings({"mode": "time", "time_seconds": None})
    assert s.time_seconds is None


async def test_snapshot_includes_teams_and_settings() -> None:
    room = Room("AAA111")
    p, _ = await room.add_player("Alex")
    t = await room.create_team("Red")
    await room.set_player_team(p.id, t.id)
    snap = room.snapshot()
    assert "teams" in snap
    assert "settings" in snap
    team = snap["teams"][0]  # type: ignore[index]
    assert team["name"] == "Red"
    assert team["player_ids"] == [p.id]
