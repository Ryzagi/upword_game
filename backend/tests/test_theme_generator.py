"""Validation tests for ThemeGenerator._build_theme — covers the post-OpenAI
parsing / validation layer without needing an actual API key."""

from __future__ import annotations

import pytest

from app.ai.theme_generator import ThemeGenerationError, ThemeGenerator


def _good_payload() -> dict:
    return {
        "name": "Space",
        "icon": "rocket",
        "words": [
            {"text": "moon",      "difficulty": 1, "hint": "We see it at night near the Earth."},
            {"text": "rocket",    "difficulty": 2, "hint": "A propelled vehicle that breaks free of gravity."},
            {"text": "asteroid",  "difficulty": 3, "hint": "A rocky chunk drifting between planets."},
            {"text": "supernova", "difficulty": 4, "hint": "A massive stellar explosion at the end of a star's life."},
            {"text": "exoplanet", "difficulty": 5, "hint": "A world orbiting a sun other than ours."},
        ],
    }


def _make_gen() -> ThemeGenerator:
    return ThemeGenerator(api_key="sk-test", model="dummy", reasoning_effort=None)


def test_build_theme_happy_path() -> None:
    gen = _make_gen()
    theme = gen._build_theme(_good_payload(), existing_ids=set())  # noqa: SLF001
    assert theme.name == "Space"
    assert len(theme.words) == 5
    assert {w.difficulty for w in theme.words} == {1, 2, 3, 4, 5}
    assert all(w.id and w.text and w.hint for w in theme.words)


def test_build_theme_id_collision_synthesises_unique_suffix() -> None:
    gen = _make_gen()
    theme = gen._build_theme(_good_payload(), existing_ids={"ai-space"})  # noqa: SLF001
    assert theme.id != "ai-space"
    assert theme.id.startswith("ai-space")


def test_build_theme_rejects_hint_that_contains_target() -> None:
    gen = _make_gen()
    payload = _good_payload()
    payload["words"][0]["hint"] = "Look up — you can see the moon at night."
    with pytest.raises(ThemeGenerationError):
        gen._build_theme(payload, existing_ids=set())  # noqa: SLF001


def test_build_theme_rejects_missing_difficulty() -> None:
    gen = _make_gen()
    payload = _good_payload()
    payload["words"][2]["difficulty"] = 1  # duplicate, no level 3
    with pytest.raises(ThemeGenerationError):
        gen._build_theme(payload, existing_ids=set())  # noqa: SLF001


def test_build_theme_rejects_wrong_word_count() -> None:
    gen = _make_gen()
    payload = _good_payload()
    payload["words"] = payload["words"][:4]
    with pytest.raises(ThemeGenerationError):
        gen._build_theme(payload, existing_ids=set())  # noqa: SLF001


def test_build_theme_rejects_empty_name() -> None:
    gen = _make_gen()
    payload = _good_payload()
    payload["name"] = ""
    with pytest.raises(ThemeGenerationError):
        gen._build_theme(payload, existing_ids=set())  # noqa: SLF001
