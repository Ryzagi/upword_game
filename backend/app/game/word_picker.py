from __future__ import annotations

import random
from collections.abc import Iterable

from app.corpus.schema import Corpus, Word


def pick_word_for_cell(
    corpus: Corpus,
    theme_id: str,
    difficulty: int,
    *,
    exclude_ids: Iterable[str] = (),
    rng: random.Random | None = None,
    extra_themes: Iterable[object] = (),
) -> Word | None:
    """Return a random word from `corpus` matching `(theme_id, difficulty)`,
    skipping anything in `exclude_ids`. Returns None if no candidates remain.

    `extra_themes` lets the caller fold in AI-generated per-room themes
    without mutating the shared corpus.
    """
    theme = next((t for t in corpus.themes if t.id == theme_id), None)
    if theme is None:
        theme = next((t for t in extra_themes if getattr(t, "id", None) == theme_id), None)
    if theme is None:
        return None
    excluded = set(exclude_ids)
    candidates = [w for w in theme.words if w.difficulty == difficulty and w.id not in excluded]
    if not candidates:
        return None
    chooser = rng or random
    return chooser.choice(candidates)


def pick_surprise_word(
    corpus: Corpus,
    difficulty: int,
    *,
    exclude_ids: Iterable[str] = (),
    rng: random.Random | None = None,
    extra_themes: Iterable[object] = (),
) -> Word | None:
    """Pick a random word of the given `difficulty` from ANY theme — the
    corpus plus any per-room generated themes. Powers the synthetic
    "Surprise me" board row. Returns None only if no theme has an unused
    word at that difficulty.
    """
    excluded = set(exclude_ids)
    candidates: list[Word] = []
    for theme in corpus.themes:
        candidates.extend(
            w for w in theme.words if w.difficulty == difficulty and w.id not in excluded
        )
    for theme in extra_themes:
        words = getattr(theme, "words", [])
        candidates.extend(
            w for w in words if w.difficulty == difficulty and w.id not in excluded
        )
    if not candidates:
        return None
    chooser = rng or random
    return chooser.choice(candidates)
