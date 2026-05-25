"""Tests for per-player theme picks and the letter-reveal mechanic."""

from __future__ import annotations

import pytest

from app.corpus.schema import Corpus
from app.models.errors import BadThemePicksError
from app.rooms.room import Room, _max_picks_per_player


# ----------------------------------------------------------- _max_picks_per_player


def test_max_picks_2_players_is_2() -> None:
    assert _max_picks_per_player(2) == 2


def test_max_picks_3_plus_players_is_1() -> None:
    assert _max_picks_per_player(3) == 1
    assert _max_picks_per_player(6) == 1


# ------------------------------------------------------------ set_player_theme_picks


async def test_set_picks_stores_them(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    first = sample_corpus_en.themes[0].id
    await room.set_player_theme_picks(p1.id, [first])
    assert room.players[p1.id].theme_picks == [first]


async def test_set_picks_dedupes(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    first = sample_corpus_en.themes[0].id
    await room.set_player_theme_picks(p1.id, [first, first])
    assert room.players[p1.id].theme_picks == [first]


async def test_set_picks_rejects_unknown_theme(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    with pytest.raises(BadThemePicksError):
        await room.set_player_theme_picks(p1.id, ["does-not-exist"])


async def test_set_picks_caps_at_two_for_2_player_room(
    sample_corpus_en: Corpus,
) -> None:
    if len(sample_corpus_en.themes) < 3:
        pytest.skip("corpus has fewer than 3 themes")
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    ids = [t.id for t in sample_corpus_en.themes[:3]]
    with pytest.raises(BadThemePicksError):
        await room.set_player_theme_picks(p1.id, ids)


async def test_set_picks_caps_at_one_for_3_player_room(
    sample_corpus_en: Corpus,
) -> None:
    if len(sample_corpus_en.themes) < 2:
        pytest.skip("corpus has fewer than 2 themes")
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    await room.add_player("Pat")
    ids = [t.id for t in sample_corpus_en.themes[:2]]
    with pytest.raises(BadThemePicksError):
        await room.set_player_theme_picks(p1.id, ids)


async def test_set_picks_rejects_theme_already_claimed_by_another(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    first = sample_corpus_en.themes[0].id
    await room.set_player_theme_picks(p1.id, [first])
    with pytest.raises(BadThemePicksError):
        await room.set_player_theme_picks(p2.id, [first])


async def test_set_picks_allows_player_to_update_their_own_picks(
    sample_corpus_en: Corpus,
) -> None:
    """A player re-setting their own picks (no overlap with others) succeeds."""
    if len(sample_corpus_en.themes) < 2:
        pytest.skip("corpus has fewer than 2 themes")
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    a = sample_corpus_en.themes[0].id
    b = sample_corpus_en.themes[1].id
    await room.set_player_theme_picks(p1.id, [a])
    await room.set_player_theme_picks(p1.id, [b])
    assert room.players[p1.id].theme_picks == [b]


async def test_start_game_blocks_when_a_player_has_no_picks(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    first = sample_corpus_en.themes[0].id
    await room.set_player_theme_picks(p1.id, [first])
    # Mira has no picks → the auto-seed fixture sees Alex has picked, so it
    # leaves Mira empty. start_game should reject.
    with pytest.raises(BadThemePicksError):
        await room.start_game()


async def test_start_game_board_uses_union_of_picks(
    sample_corpus_en: Corpus,
) -> None:
    if len(sample_corpus_en.themes) < 2:
        pytest.skip("corpus has fewer than 2 themes")
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    a = sample_corpus_en.themes[0].id
    b = sample_corpus_en.themes[1].id
    await room.set_player_theme_picks(p1.id, [a])
    await room.set_player_theme_picks(p2.id, [b])
    await room.start_game()
    assert room.board is not None
    board_ids = [t["id"] for t in room.board.themes]
    assert set(board_ids) == {a, b}


async def test_start_game_uses_all_distinct_picks(
    sample_corpus_en: Corpus,
) -> None:
    """Theme picks are exclusive — distinct picks all appear on the board."""
    if len(sample_corpus_en.themes) < 2:
        pytest.skip("corpus has fewer than 2 themes")
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    a = sample_corpus_en.themes[0].id
    b = sample_corpus_en.themes[1].id
    await room.set_player_theme_picks(p1.id, [a])
    await room.set_player_theme_picks(p2.id, [b])
    await room.start_game()
    assert room.board is not None
    assert set(t["id"] for t in room.board.themes) == {a, b}


# ------------------------------------------------------------------ letter pattern


async def test_letter_pattern_masks_initially(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer_id = room._current_describer_id_locked()
    theme_id = room.board.theme_ids[0]
    rnd = await room.pick_cell(describer_id, theme_id, 1)
    pattern = rnd.letter_pattern()
    for i, ch in enumerate(rnd.word_text):
        if ch.isspace():
            assert pattern[i] == ch
        else:
            assert pattern[i] == "_"


async def test_letter_pattern_reveals_index(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer_id = room._current_describer_id_locked()
    theme_id = room.board.theme_ids[0]
    rnd = await room.pick_cell(describer_id, theme_id, 1)
    hidden = rnd.hidden_letter_indices()
    assert hidden, "expected at least one letter to reveal"
    idx = hidden[0]
    rnd.revealed_indices.add(idx)
    pattern = rnd.letter_pattern()
    assert pattern[idx] == rnd.word_text[idx]
    for j in hidden[1:]:
        assert pattern[j] == "_"


async def test_round_public_includes_letter_fields(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer_id = room._current_describer_id_locked()
    theme_id = room.board.theme_ids[0]
    rnd = await room.pick_cell(describer_id, theme_id, 1)
    pub = rnd.public()
    assert "letter_pattern" in pub
    assert "letter_count" in pub
    assert "revealed_indices" in pub
    assert pub["letter_count"] == sum(1 for ch in rnd.word_text if not ch.isspace())
    assert pub["revealed_indices"] == []
