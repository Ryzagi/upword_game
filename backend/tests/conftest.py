from __future__ import annotations

from pathlib import Path

import pytest

from app.corpus.loader import load_corpus
from app.corpus.schema import Corpus

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_EN = REPO_ROOT / "data" / "words.sample.en.json"


@pytest.fixture(scope="session")
def sample_corpus_en() -> Corpus:
    return load_corpus(SAMPLE_EN)


@pytest.fixture(scope="session")
def corpora(sample_corpus_en: Corpus) -> dict[str, Corpus]:
    return {sample_corpus_en.language: sample_corpus_en}


@pytest.fixture(autouse=True)
def _auto_seed_theme_picks(monkeypatch):
    """Legacy tests don't set theme picks. Auto-seed them with the first
    theme so `start_game` validation passes — but only when nobody picked
    anything (so dedicated theme-pick tests can still exercise validation
    by setting picks on some players and leaving others empty).
    """
    from app.rooms.room import Room

    orig_start = Room.start_game

    async def patched_start(self: Room):  # type: ignore[override]
        if self.corpus is not None and self.players:
            any_picked = any(p.theme_picks for p in self.players.values())
            if not any_picked and self.corpus.themes:
                first = self.corpus.themes[0].id
                for p in self.players.values():
                    p.theme_picks = [first]
        return await orig_start(self)

    monkeypatch.setattr(Room, "start_game", patched_start)
