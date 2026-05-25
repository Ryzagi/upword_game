"""Phase 6 — full coverage on the guess normaliser."""

from __future__ import annotations

from app.corpus.loader import normalise


def test_empty_and_whitespace_collapse_to_empty() -> None:
    assert normalise("") == ""
    assert normalise("   ") == ""
    assert normalise("\t\n  \t") == ""


def test_case_folds_to_lowercase() -> None:
    assert normalise("Hello") == "hello"
    assert normalise("HELLO") == "hello"
    assert normalise("ПрИвЕт") == "привет"


def test_strips_diacritics() -> None:
    assert normalise("café") == "cafe"
    assert normalise("naïve") == "naive"
    assert normalise("Pötzlich") == "potzlich"
    # ё → е (because the combining diaeresis is stripped).
    assert normalise("кёрлинг") == "керлинг"


def test_collapses_internal_whitespace() -> None:
    assert normalise("a    b") == "a b"
    assert normalise("a\tb\nc") == "a b c"
    assert normalise("  trimmed  ") == "trimmed"


def test_strips_punctuation_to_word_boundaries() -> None:
    assert normalise("Ice-cream!") == "ice cream"
    assert normalise("ice cream") == "ice cream"
    assert normalise("hello, world!") == "hello world"
    assert normalise("don't") == "don t"


def test_handles_mixed_punctuation_and_case() -> None:
    assert normalise("  Ice-Cream!?  ") == "ice cream"
    assert normalise("Don't…  go") == "don t go"


def test_cyrillic_punctuation_strips() -> None:
    assert normalise("Привет, мир!") == "привет мир"


def test_unicode_combining_marks_handled() -> None:
    # Composed and decomposed forms of "é" should normalise the same.
    composed = "Café"  # é as a single codepoint
    decomposed = "Café"  # e + combining acute
    assert normalise(composed) == normalise(decomposed) == "cafe"


def test_multiple_hyphens_compounds() -> None:
    assert normalise("twenty-one-thousand") == "twenty one thousand"
    assert normalise("up-to-date") == "up to date"


def test_emoji_left_intact() -> None:
    # Emoji aren't in any of our target words; left as-is just makes
    # normalised guesses harmlessly mismatch.
    out = normalise("hello 🌍 world")
    assert "hello" in out and "world" in out


def test_preserves_internal_letters_across_punctuation() -> None:
    assert normalise("can't stop won't stop") == "can t stop won t stop"
