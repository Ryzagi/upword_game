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
) -> Word | None:
    """Return a random word from `corpus` matching `(theme_id, difficulty)`,
    skipping anything in `exclude_ids`. Returns None if no candidates remain.
    """
    theme = next((t for t in corpus.themes if t.id == theme_id), None)
    if theme is None:
        return None
    excluded = set(exclude_ids)
    candidates = [w for w in theme.words if w.difficulty == difficulty and w.id not in excluded]
    if not candidates:
        return None
    chooser = rng or random
    return chooser.choice(candidates)
