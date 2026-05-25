import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from app.corpus.schema import Corpus


def normalise(text: str) -> str:
    """Normalise text for guess/target comparison.

    Lowercase (Unicode-aware), strip diacritics, replace punctuation with
    spaces (so "ice-cream" matches "ice cream"), and collapse whitespace.
    """
    decomposed = unicodedata.normalize("NFD", text.casefold())
    pieces: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch):
            continue
        if unicodedata.category(ch).startswith("P"):
            pieces.append(" ")
        else:
            pieces.append(ch)
    return " ".join("".join(pieces).split())


def _contains_word_phrase(haystack: str, needle: str) -> bool:
    """Return True if needle appears in haystack as a word-aligned subsequence.

    Both inputs are expected to be normalised (lowercase, single-spaced).
    """
    haystack_words = haystack.split()
    needle_words = needle.split()
    if not needle_words:
        return False
    n = len(needle_words)
    return any(
        haystack_words[i : i + n] == needle_words for i in range(len(haystack_words) - n + 1)
    )


def _validate(corpus: Corpus) -> None:
    theme_ids = [t.id for t in corpus.themes]
    if len(theme_ids) != len(set(theme_ids)):
        raise ValueError(f"Duplicate theme ids in corpus for language {corpus.language!r}")

    for theme in corpus.themes:
        word_ids = [w.id for w in theme.words]
        if len(word_ids) != len(set(word_ids)):
            raise ValueError(f"Duplicate word ids in theme {theme.id!r}")

        by_diff: dict[int, list[str]] = defaultdict(list)
        for w in theme.words:
            by_diff[w.difficulty].append(w.id)
        for d in range(1, 6):
            if not by_diff[d]:
                raise ValueError(
                    f"Theme {theme.id!r} (language {corpus.language!r}) "
                    f"has no word at difficulty {d}"
                )

        for w in theme.words:
            target = normalise(w.text)
            hint = normalise(w.hint)
            if _contains_word_phrase(hint, target):
                raise ValueError(f"Hint for word {w.text!r} contains target after normalisation")


def load_corpus(path: Path) -> Corpus:
    """Load and validate a single corpus JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    corpus = Corpus.model_validate(raw)
    _validate(corpus)
    return corpus


def load_all_corpora(directory: Path) -> dict[str, Corpus]:
    """Load every words.*.json file in the given directory, keyed by language."""
    out: dict[str, Corpus] = {}
    for path in sorted(directory.glob("words.*.json")):
        corpus = load_corpus(path)
        if corpus.language in out:
            raise ValueError(
                f"Duplicate corpus for language {corpus.language!r} (second file: {path})"
            )
        out[corpus.language] = corpus
    return out
