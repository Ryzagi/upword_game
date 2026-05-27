"""Phase 3 — Room state machine tests.

Covers start_game (solo and teams), pick_cell (validation + word picking),
concede, force_end, play_again, board exhaustion → game_ended, and the
describer-leaves-mid-round auto-end behaviour.
"""

from __future__ import annotations

import pytest

from app.corpus.schema import Corpus
from app.models.errors import (
    BadTeamConfigError,
    CellAlreadyUsedError,
    NotDescriberError,
    NotEnoughPlayersError,
    RoomNotInLobbyError,
    RoomNotOnBoardError,
    RoundNotActiveError,
    UnknownThemeError,
)
from app.rooms.room import Room

# ----------------------------------------------------------------- start_game


async def test_start_game_in_solo_creates_one_team_per_player(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    p3, _ = await room.add_player("Pat")

    await room.start_game()

    assert room.state == "board"
    assert len(room.teams) == 3
    for player in room.players.values():
        assert player.team_id is not None
    # Each team has exactly one member.
    for team in room.teams.values():
        members = [p for p in room.players.values() if p.team_id == team.id]
        assert len(members) == 1
    # Rotation includes every player.
    assert set(room.rotation) == {p1.id, p2.id, p3.id}


async def test_start_game_in_teams_uses_existing_assignments(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    await room.update_settings({"team_mode": "teams"})
    red = await room.create_team("Red")
    blue = await room.create_team("Blue")
    await room.set_player_team(p1.id, red.id)
    await room.set_player_team(p2.id, blue.id)

    await room.start_game()

    assert room.state == "board"
    assert room.players[p1.id].team_id == red.id
    assert room.players[p2.id].team_id == blue.id


async def test_start_game_rejects_with_too_few_players(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    with pytest.raises(NotEnoughPlayersError):
        await room.start_game()


async def test_start_game_rejects_when_already_started(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    with pytest.raises(RoomNotInLobbyError):
        await room.start_game()


async def test_start_game_rejects_in_teams_mode_with_empty_team(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    await room.update_settings({"team_mode": "teams"})
    red = await room.create_team("Red")
    await room.create_team("Blue")  # empty
    await room.set_player_team(p1.id, red.id)
    # Mira has no team_id assigned → also a config error.
    with pytest.raises(BadTeamConfigError):
        await room.start_game()


async def test_start_game_resets_team_scores(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.update_settings({"team_mode": "teams"})
    red = await room.create_team("Red")
    blue = await room.create_team("Blue")
    # pretend they had scores from a prior game
    room.teams[red.id].score = 250
    room.teams[blue.id].score = 100
    # assign players
    for pid in list(room.players):
        await room.set_player_team(pid, red.id if pid == next(iter(room.players)) else blue.id)
    await room.start_game()
    for team in room.teams.values():
        assert team.score == 0


# ----------------------------------------------------------------- pick_cell


async def test_pick_cell_rejects_non_describer(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    await room.start_game()
    other = (
        p2.id
        if room.current_describer_id != p2.id
        else next(iter(p for p in room.players if p != p2.id))
    )
    with pytest.raises(NotDescriberError):
        await room.pick_cell(other, "sport", 1)


async def test_pick_cell_succeeds_for_describer(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    round_obj = await room.pick_cell(describer, "sport", 3)
    assert room.state == "round"
    assert room.current_round is round_obj
    assert round_obj.theme_id == "sport"
    assert round_obj.difficulty == 3
    assert round_obj.base_score == 300
    assert round_obj.word_text  # describer sees this
    assert room.board is not None
    assert room.board.is_used("sport", 3)


async def test_pick_cell_rejects_unknown_theme(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    with pytest.raises(UnknownThemeError):
        await room.pick_cell(describer, "phantom-theme", 3)


async def test_pick_cell_rejects_used_cell(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 3)
    # End the round via the host-side force-end (concede is now a guesser
    # action and only ends the round once everyone's finished).
    await room.force_end_round()
    # next describer now in seat
    next_describer = room.current_describer_id
    assert next_describer is not None
    with pytest.raises(CellAlreadyUsedError):
        await room.pick_cell(next_describer, "sport", 3)


async def test_pick_cell_rejects_when_not_on_board(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    with pytest.raises(RoomNotOnBoardError):
        await room.pick_cell("anyone", "sport", 1)


# --------------------------------------------------------------- concede flow


async def test_concede_by_last_guesser_ends_round(
    sample_corpus_en: Corpus,
) -> None:
    """When the only guesser concedes, the round ends naturally."""
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    guesser = next(pid for pid in room.players if pid != describer)
    _, ended = await room.concede(guesser)
    assert ended is True
    assert room.state == "board"
    assert room.current_round is None
    assert room.current_describer_id != describer


async def test_concede_rejected_for_describer(
    sample_corpus_en: Corpus,
) -> None:
    """The describer isn't a guesser — they can't concede."""
    from app.models.errors import DescriberCannotGuessError

    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    with pytest.raises(DescriberCannotGuessError):
        await room.concede(describer)


async def test_concede_does_not_end_round_when_others_still_trying(
    sample_corpus_en: Corpus,
) -> None:
    """In a 3-player room, one guesser conceding leaves the second still
    in the round — the round doesn't end yet."""
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.add_player("Pat")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    guessers = [pid for pid in room.players if pid != describer]
    _, ended = await room.concede(guessers[0])
    assert ended is False
    assert room.state == "round"
    # The second guesser conceding finishes everyone off → round ends.
    _, ended = await room.concede(guessers[1])
    assert ended is True
    assert room.state == "board"


async def test_concede_rejected_when_no_round(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    other = next(iter(room.players))
    with pytest.raises(RoundNotActiveError):
        await room.concede(other)


# --------------------------------------------------------------- force_end


async def test_force_end_round_works_outside_describer(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    ended = await room.force_end_round()
    assert ended.state == "ended"
    assert room.state == "board"


# --------------------------------------------- describer leaves mid-round


async def test_describer_leaves_mid_round_auto_ends(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)

    result = await room.remove_player(describer)
    assert result.removed
    assert result.round_ended is not None
    assert result.round_ended.state == "ended"
    assert room.state == "board"
    assert room.current_describer_id != describer  # rotation skipped them


# ------------------------------------------------------- board exhaustion


async def test_game_ends_when_board_full(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    assert room.board is not None
    total = room.board.total_cells
    for _ in range(total):
        describer = room.current_describer_id
        assert describer is not None
        # Pick the first unused cell
        cell = next(
            (t, d)
            for t in room.board.theme_ids
            for d in range(1, len(room.board.base_values) + 1)
            if not room.board.is_used(t, d)
        )
        await room.pick_cell(describer, cell[0], cell[1])
        await room.force_end_round()
    assert room.state == "ended"
    assert room.board.is_full()


# --------------------------------------------------------------- play_again


async def test_play_again_resets_to_lobby_and_clears_picks(
    sample_corpus_en: Corpus,
) -> None:
    """After play_again the room returns to the lobby so players can
    re-pick themes for the next game."""
    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    p_mira, _ = await room.add_player("Mira")
    await room.start_game()
    # Confirm picks were auto-seeded by the test fixture.
    assert room.players[p_alex.id].theme_picks
    # Play through full board.
    assert room.board is not None
    total = room.board.total_cells
    for _ in range(total):
        describer = room.current_describer_id
        assert describer is not None
        cell = next(
            (t, d)
            for t in room.board.theme_ids
            for d in range(1, len(room.board.base_values) + 1)
            if not room.board.is_used(t, d)
        )
        await room.pick_cell(describer, cell[0], cell[1])
        await room.force_end_round()
    assert room.state == "ended"
    # Mess with a team score to verify it resets.
    next(iter(room.teams.values())).score = 999

    await room.play_again()

    assert room.state == "lobby"
    assert room.board is None
    assert all(t.score == 0 for t in room.teams.values())
    # Every player has an empty theme pick list now, so they have to
    # re-pick before the next start_game.
    assert all(p.theme_picks == [] for p in room.players.values())
    _ = p_mira  # silence unused warning


# --------------------------------------------------------- snapshot privacy


async def test_snapshot_does_not_include_word(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    round_obj = await room.pick_cell(describer, "sport", 1)
    snap = room.snapshot()
    assert "current_round" in snap
    # The public form must not leak the word.
    public_round = snap["current_round"]
    assert isinstance(public_round, dict)
    assert "word_text" not in public_round
    assert "hint" not in public_round
    # The private accessor returns the word for the describer only.
    private = room.private_round_info_for(describer)
    assert private is not None
    assert private["word_text"] == round_obj.word_text
    # And NOT for anyone else.
    other = next(pid for pid in room.players if pid != describer)
    assert room.private_round_info_for(other) is None


# ------------------------------------------------------------ word non-repeat


async def test_words_dont_repeat_within_a_game(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    assert room.board is not None
    seen_words: set[str] = set()
    # Play through every cell and record the word_ids picked.
    total = room.board.total_cells
    for _ in range(total):
        describer = room.current_describer_id
        assert describer is not None
        cell = next(
            (t, d)
            for t in room.board.theme_ids
            for d in range(1, len(room.board.base_values) + 1)
            if not room.board.is_used(t, d)
        )
        round_obj = await room.pick_cell(describer, cell[0], cell[1])
        assert round_obj.word_id not in seen_words
        seen_words.add(round_obj.word_id)
        await room.force_end_round()
