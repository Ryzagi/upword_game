"""Regression: when the round's deadline fires from the timer task itself,
`_finalize_round_locked` must not cancel that very task — otherwise the
subsequent `await` to release the room lock raises CancelledError and the
broadcast of `round/ended` / `board/state` never lands on clients.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.corpus.loader import load_corpus
from app.rooms.room import Room


@pytest.mark.asyncio
async def test_finalize_does_not_cancel_self_task() -> None:
    corpus = load_corpus(Path(__file__).resolve().parents[2] / "data" / "words.sample.en.json")
    room = Room("TEST01", corpus=corpus)
    await room.add_player("Alex")
    await room.add_player("Mira")
    await room.start_game()
    describer = room.current_describer_id
    assert describer is not None
    await room.pick_cell(describer, "sport", 1)
    # Pretend the timer task IS the current task — this is what happens when
    # the real `_round_timer_task` calls force_end_round on time-up.
    room._round_end_task = asyncio.current_task()
    ended = await room.force_end_round()
    # If self-cancel were happening, `async with self.lock` exit inside
    # force_end_round would raise CancelledError before we get here.
    assert ended.state == "ended"
    assert room._round_end_task is None
