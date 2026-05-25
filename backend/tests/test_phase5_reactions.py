"""Phase 5 — reactions backend tests."""

from __future__ import annotations

import pytest

from app.corpus.schema import Corpus
from app.models.errors import RoundNotActiveError
from app.rooms.room import Room


async def _start_round(room: Room) -> tuple[str, str]:
    """Build a 2-player solo game, pick Sport·1, return (describer, guesser)."""
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    guesser = next(pid for pid in room.players if pid != describer)
    return describer, guesser


async def test_toggle_reaction_adds_like(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    describer, guesser = await _start_round(room)
    state = await room.toggle_reaction(guesser, "like")
    assert state == {"likes": [guesser], "dislikes": []}


async def test_same_kind_toggles_off(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    describer, guesser = await _start_round(room)
    await room.toggle_reaction(guesser, "like")
    state = await room.toggle_reaction(guesser, "like")
    assert state == {"likes": [], "dislikes": []}


async def test_different_kind_replaces(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    describer, guesser = await _start_round(room)
    await room.toggle_reaction(guesser, "like")
    state = await room.toggle_reaction(guesser, "dislike")
    assert state == {"likes": [], "dislikes": [guesser]}


async def test_invalid_kind_raises(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    describer, guesser = await _start_round(room)
    with pytest.raises(ValueError, match="invalid_payload"):
        await room.toggle_reaction(guesser, "frown")


async def test_react_when_no_round_raises(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    await room.add_player("Alex")
    p2, _ = await room.add_player("Mira")
    await room.start_game()
    with pytest.raises(RoundNotActiveError):
        await room.toggle_reaction(p2.id, "like")


async def test_reactions_reset_when_new_round_picks(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    describer, guesser = await _start_round(room)
    await room.toggle_reaction(guesser, "like")
    assert room.current_round is not None
    assert guesser in room.current_round.reactions
    # End the round, start the next round
    await room.concede(describer)
    assert room.state == "board"
    next_describer = room.current_describer_id
    assert next_describer is not None
    await room.pick_cell(next_describer, "sport", 2)
    assert room.current_round is not None
    # Fresh round → no reactions
    assert room.current_round.reactions == {}


async def test_reactions_appear_in_round_public(sample_corpus_en: Corpus) -> None:
    room = Room("AAA111", corpus=sample_corpus_en)
    describer, guesser = await _start_round(room)
    await room.toggle_reaction(guesser, "like")
    assert room.current_round is not None
    pub = room.current_round.public()
    assert pub["reactions"] == {"likes": [guesser], "dislikes": []}
