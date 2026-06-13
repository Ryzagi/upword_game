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


async def test_play_again_refreshes_theme_gen_allowance(
    sample_corpus_en: Corpus,
) -> None:
    """Returning to the lobby grants each player a fresh generation
    allowance, while the previously generated themes stick around."""
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
        # Alex has exhausted his allowance.
        allowed, _ = room.can_generate_theme_locked(p_alex.id)
        assert allowed is False
        themes_before = len(room.extra_themes)

    # Play a trivial game to completion so we can call play_again.
    # Seed picks so start_game passes, then exhaust the board via force_end.
    await room.set_player_theme_picks(p_alex.id, [sample_corpus_en.themes[0].id])
    for pid in room.players:
        if pid != p_alex.id:
            await room.set_player_theme_picks(pid, [sample_corpus_en.themes[1].id])
    await room.start_game()
    # Burn the board down to end the game.
    while room.state != "ended":
        describer = room.current_describer_id
        assert describer is not None
        # Find an unused cell.
        cell = next(
            (theme_id, d)
            for theme_id in room.board.theme_ids
            for d in range(1, len(room.board.base_values) + 1)
            if not room.board.is_used(theme_id, d)
        )
        await room.pick_cell(describer, cell[0], cell[1])
        await room.force_end_round()

    await room.play_again()

    async with room.lock:
        # Themes persisted...
        assert len(room.extra_themes) == themes_before
        # ...but the allowance is refreshed.
        allowed, code = room.can_generate_theme_locked(p_alex.id)
        assert allowed is True
        assert code is None
        assert room.generated_count_for_player_locked(p_alex.id) == 0


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


# ----------------------------------------------------------- lightning cells


async def test_lightning_cell_multiplies_base_score(sample_corpus_en: Corpus) -> None:
    """A lightning cell scales the round's base_score by its multiplier."""
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    theme_id = room.board.theme_ids[0]
    # Force a known lightning multiplier on the cell we'll pick.
    room.board.lightning = {(theme_id, 2): 2.0}
    rnd = await room.pick_cell(describer, theme_id, 2)
    # base value at difficulty 2 is 200 → ×2 = 400.
    assert rnd.base_score == 400
    assert rnd.score_multiplier == 2.0


async def test_non_lightning_cell_unscaled(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    theme_id = room.board.theme_ids[0]
    room.board.lightning = {}
    rnd = await room.pick_cell(describer, theme_id, 2)
    assert rnd.base_score == 200
    assert rnd.score_multiplier == 1.0


def test_assign_lightning_respects_cap_and_difficulty_range() -> None:
    import random

    from app.game.board import LIGHTNING_MAX_CELLS, LIGHTNING_MULTIPLIERS, Board

    themes = [{"id": f"t{i}", "name": f"T{i}"} for i in range(8)]  # 8×5 = 40 cells
    board = Board(themes=themes)
    board.assign_lightning(rng=random.Random(42))
    assert 1 <= len(board.lightning) <= LIGHTNING_MAX_CELLS
    for (tid, diff), mult in board.lightning.items():
        assert tid in board.theme_ids
        assert 1 <= diff <= len(board.base_values)
        assert mult in LIGHTNING_MULTIPLIERS
    # Exposed in public().
    pub = board.public()
    assert "lightning" in pub
    assert len(pub["lightning"]) == len(board.lightning)


# --------------------------------------------------------- surprise-me theme


async def test_surprise_theme_is_pickable_and_serves_words(
    sample_corpus_en: Corpus,
) -> None:
    from app.rooms.room import SURPRISE_THEME_ID

    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    p_mira, _ = await room.add_player("Mira")
    # Alex picks surprise, Mira picks a real theme.
    await room.set_player_theme_picks(p_alex.id, [SURPRISE_THEME_ID])
    await room.set_player_theme_picks(p_mira.id, [sample_corpus_en.themes[0].id])
    await room.start_game()

    assert room.board is not None
    assert SURPRISE_THEME_ID in room.board.theme_ids

    # Pick every difficulty of the surprise row — each must serve a word.
    while room.current_describer_id is not None and room.state == "board":
        if not room.board.has_cell(SURPRISE_THEME_ID, 1):
            break
        # Find an unused surprise cell.
        unused = next(
            (
                d
                for d in range(1, len(room.board.base_values) + 1)
                if not room.board.is_used(SURPRISE_THEME_ID, d)
            ),
            None,
        )
        if unused is None:
            break
        describer = room.current_describer_id
        rnd = await room.pick_cell(describer, SURPRISE_THEME_ID, unused)
        assert rnd.word_text
        assert rnd.theme_id == SURPRISE_THEME_ID
        await room.force_end_round()


async def test_surprise_theme_in_pickable_list(sample_corpus_en: Corpus) -> None:
    from app.rooms.room import SURPRISE_THEME_ID

    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    await room.add_player("Mira")
    async with room.lock:
        themes = room._pickable_themes_public_locked()
    ids = [t["id"] for t in themes]
    assert SURPRISE_THEME_ID in ids
    surprise = next(t for t in themes if t["id"] == SURPRISE_THEME_ID)
    assert surprise.get("surprise") is True


# ------------------------------------------------- delete / regenerate themes


def _gen_theme(idx: int):
    from app.corpus.schema import Theme, Word

    return Theme(
        id=f"ai-test-{idx}",
        name=f"Test {idx}",
        icon=None,
        words=[
            Word(id=f"w{idx}-{d}", text=f"w{idx}-{d}", difficulty=d, hint="A word.")
            for d in (1, 2, 3, 4, 5)
        ],
    )


async def test_delete_generated_theme_frees_slot_and_picks(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    async with room.lock:
        room.add_generated_theme(_gen_theme(0), p_alex.id, prompt="space")
    # Alex picks his generated theme.
    await room.set_player_theme_picks(p_alex.id, ["ai-test-0"])
    assert room.generated_count_for_player_locked(p_alex.id) == 1

    await room.delete_generated_theme("ai-test-0", p_alex.id)

    assert "ai-test-0" not in room.extra_themes
    assert room.generated_count_for_player_locked(p_alex.id) == 0
    assert room.players[p_alex.id].theme_picks == []


async def test_delete_generated_theme_forbidden_for_other_non_host(
    sample_corpus_en: Corpus,
) -> None:
    from app.models.errors import ThemeActionForbiddenError

    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")  # Alex is host (first joiner)
    p_mira, _ = await room.add_player("Mira")
    async with room.lock:
        room.add_generated_theme(_gen_theme(0), p_alex.id)
    # Make sure Mira isn't the host.
    assert room.host_id == p_alex.id
    with pytest.raises(ThemeActionForbiddenError):
        await room.delete_generated_theme("ai-test-0", p_mira.id)


async def test_delete_unknown_theme_raises(sample_corpus_en: Corpus) -> None:
    from app.models.errors import ThemeNotFoundError

    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    with pytest.raises(ThemeNotFoundError):
        await room.delete_generated_theme("ai-nope", p_alex.id)


async def test_regenerate_swaps_words_keeps_identity(
    sample_corpus_en: Corpus,
) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    p_alex, _ = await room.add_player("Alex")
    await room.add_player("Mira")
    async with room.lock:
        room.add_generated_theme(_gen_theme(0), p_alex.id, prompt="space")
        # Simulate the cooldown having elapsed since generation.
        room._theme_gen_last_at.clear()
        prompt, exclude = room.begin_regenerate_locked("ai-test-0", p_alex.id)
        assert prompt == "space"
        assert len(exclude) == 5
        fresh = _gen_theme(99)  # different words
        room.apply_regenerated_theme_locked("ai-test-0", fresh)
        theme = room.extra_themes["ai-test-0"]
    # Same id + name + attribution, new words.
    assert theme.id == "ai-test-0"
    assert theme.name == "Test 0"
    assert room.theme_generators["ai-test-0"] == p_alex.id
    assert {w.text for w in theme.words} == {f"w99-{d}" for d in (1, 2, 3, 4, 5)}
