"""Tests for per-player theme picks and the letter-reveal mechanic."""

from __future__ import annotations

import pytest

from app.corpus.schema import Corpus
from app.models.errors import BadThemePicksError
from app.rooms.room import Room, _max_picks_per_player


# ----------------------------------------------------------- _max_picks_per_player


def test_max_picks_is_two_regardless_of_player_count() -> None:
    """Every player can pick 1–2 themes, regardless of room size."""
    assert _max_picks_per_player(2) == 2
    assert _max_picks_per_player(3) == 2
    assert _max_picks_per_player(6) == 2


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


async def test_can_generate_theme_blocks_after_player_cap(
    sample_corpus_en: Corpus,
) -> None:
    """A single player can have at most MAX_GENERATED_THEMES_PER_PLAYER
    themes in this room. The third request is rate-error capped."""
    from app.corpus.schema import Theme, Word
    from app.rooms.room import MAX_GENERATED_THEMES_PER_PLAYER

    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    await room.add_player("Mira")

    def _theme(idx: int) -> Theme:
        return Theme(
            id=f"ai-test-{idx}",
            name=f"Test {idx}",
            icon=None,
            words=[
                Word(id=f"w{idx}-{d}", text=f"w{idx}-{d}", difficulty=d, hint="A word.")
                for d in (1, 2, 3, 4, 5)
            ],
        )

    async with room.lock:
        for i in range(MAX_GENERATED_THEMES_PER_PLAYER):
            room.add_generated_theme(_theme(i), p_alex.id)
        allowed, code = room.can_generate_theme_locked(p_alex.id)

    assert allowed is False
    assert code == "theme_gen_cap_reached"


async def test_can_generate_theme_still_allowed_for_a_different_player(
    sample_corpus_en: Corpus,
) -> None:
    """Player A's cap doesn't block Player B."""
    from app.corpus.schema import Theme, Word
    from app.rooms.room import MAX_GENERATED_THEMES_PER_PLAYER

    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    p_mira, _ = await room.add_player("Mira")

    async with room.lock:
        for i in range(MAX_GENERATED_THEMES_PER_PLAYER):
            room.add_generated_theme(
                Theme(
                    id=f"ai-alex-{i}",
                    name=f"Alex {i}",
                    icon=None,
                    words=[
                        Word(
                            id=f"alex-{i}-{d}",
                            text=f"alex-{i}-{d}",
                            difficulty=d,
                            hint="A word.",
                        )
                        for d in (1, 2, 3, 4, 5)
                    ],
                ),
                p_alex.id,
            )
        # Alex is capped.
        a_allowed, a_code = room.can_generate_theme_locked(p_alex.id)
        # Mira has used 0 generations — should be allowed (modulo cooldown,
        # which she hasn't triggered yet).
        m_allowed, m_code = room.can_generate_theme_locked(p_mira.id)

    assert a_allowed is False and a_code == "theme_gen_cap_reached"
    assert m_allowed is True and m_code is None


async def test_set_picks_caps_at_two_for_3_player_room(
    sample_corpus_en: Corpus,
) -> None:
    """Even in a 3+ player room every player can still pick up to 2 themes —
    three picks must be rejected."""
    if len(sample_corpus_en.themes) < 3:
        pytest.skip("corpus has fewer than 3 themes")
    room = Room("AAA111", corpus=sample_corpus_en)
    p1, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    await room.add_player("Pat")
    # Two picks → fine.
    two_ids = [t.id for t in sample_corpus_en.themes[:2]]
    await room.set_player_theme_picks(p1.id, two_ids)
    # Three picks → rejected.
    three_ids = [t.id for t in sample_corpus_en.themes[:3]]
    with pytest.raises(BadThemePicksError):
        await room.set_player_theme_picks(p1.id, three_ids)


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


async def test_ai_generated_theme_cell_picks_correctly(
    sample_corpus_en: Corpus,
) -> None:
    """Regression: an AI-generated theme (stored in extra_themes, not the
    shared corpus) must serve a word when its cell is picked on the board.
    """
    from app.corpus.schema import Theme, Word

    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    p_mira, _ = await room.add_player("Mira")

    fake_theme = Theme(
        id="ai-space",
        name="Space",
        icon="rocket",
        words=[
            Word(id="moon",      text="moon",      difficulty=1, hint="Visible at night."),
            Word(id="rocket",    text="rocket",    difficulty=2, hint="Propelled vehicle that escapes gravity."),
            Word(id="asteroid",  text="asteroid",  difficulty=3, hint="Rocky drifting body between planets."),
            Word(id="supernova", text="supernova", difficulty=4, hint="Cataclysmic stellar explosion."),
            Word(id="exoplanet", text="exoplanet", difficulty=5, hint="World orbiting another sun."),
        ],
    )
    async with room.lock:
        room.add_generated_theme(fake_theme, p_alex.id)
    await room.set_player_theme_picks(p_alex.id, ["ai-space"])
    await room.set_player_theme_picks(p_mira.id, [sample_corpus_en.themes[0].id])
    await room.start_game()

    # The describer picks every difficulty of the AI theme — all five should
    # serve a word without raising NoWordsAvailableError.
    for difficulty in range(1, 6):
        describer = room.current_describer_id
        rnd = await room.pick_cell(describer, "ai-space", difficulty)
        assert rnd.word_text  # non-empty
        # End the round so the board comes back and rotation advances.
        await room.force_end_round()


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
