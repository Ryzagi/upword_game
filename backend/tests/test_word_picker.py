from __future__ import annotations

import random

from app.corpus.schema import Corpus, Theme, Word
from app.game.word_picker import pick_word_for_cell


def _corpus_with(theme_id: str, words: list[Word]) -> Corpus:
    return Corpus(
        version=1,
        language="en",
        themes=[Theme(id=theme_id, name=theme_id.title(), words=words)],
    )


def _w(id: str, text: str, difficulty: int, hint: str = "a hint") -> Word:
    return Word(id=id, text=text, difficulty=difficulty, hint=hint)


def test_picks_a_matching_word() -> None:
    corpus = _corpus_with(
        "test",
        [
            _w("a", "alpha", 1),
            _w("b", "bravo", 2),
            _w("c", "charlie", 3),
        ],
    )
    word = pick_word_for_cell(corpus, "test", 2, rng=random.Random(0))
    assert word is not None
    assert word.id == "b"
    assert word.difficulty == 2


def test_excludes_used_ids() -> None:
    corpus = _corpus_with(
        "test",
        [
            _w("a", "alpha", 1),
            _w("a2", "alpha2", 1),
        ],
    )
    word = pick_word_for_cell(corpus, "test", 1, exclude_ids=["a"], rng=random.Random(0))
    assert word is not None
    assert word.id == "a2"


def test_returns_none_if_nothing_matches() -> None:
    corpus = _corpus_with("test", [_w("a", "alpha", 1)])
    assert pick_word_for_cell(corpus, "test", 5) is None


def test_returns_none_if_theme_missing() -> None:
    corpus = _corpus_with("test", [_w("a", "alpha", 1)])
    assert pick_word_for_cell(corpus, "ghost", 1) is None


def test_returns_none_when_everything_is_excluded() -> None:
    corpus = _corpus_with("test", [_w("a", "alpha", 1)])
    assert pick_word_for_cell(corpus, "test", 1, exclude_ids=["a"]) is None
