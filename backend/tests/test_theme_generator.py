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


# ----------------------------------------------------------------- retry loop


async def test_generate_retries_bad_response_then_succeeds(monkeypatch) -> None:
    """If the model returns a payload that fails validation the first time,
    `generate` retries — and a subsequent good response should succeed."""
    gen = _make_gen()

    call_count = 0
    bad_payload = _good_payload()
    bad_payload["words"] = bad_payload["words"][:3]  # only 3 words → bad_response
    good_payload = _good_payload()

    async def fake_once(*, prompt, language, existing_theme_ids):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return gen._build_theme(bad_payload, existing_theme_ids)  # noqa: SLF001 — raises
        return gen._build_theme(good_payload, existing_theme_ids)  # noqa: SLF001

    monkeypatch.setattr(gen, "_generate_once", fake_once)
    theme = await gen.generate(prompt="x", language="en", existing_theme_ids=set())
    assert theme.name == "Space"
    assert call_count == 2


async def test_generate_gives_up_after_max_attempts(monkeypatch) -> None:
    from app.ai.theme_generator import GENERATION_MAX_ATTEMPTS

    gen = _make_gen()
    bad_payload = _good_payload()
    bad_payload["words"] = bad_payload["words"][:3]

    call_count = 0

    async def fake_once(*, prompt, language, existing_theme_ids):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        return gen._build_theme(bad_payload, existing_theme_ids)  # noqa: SLF001

    monkeypatch.setattr(gen, "_generate_once", fake_once)
    with pytest.raises(ThemeGenerationError):
        await gen.generate(prompt="x", language="en", existing_theme_ids=set())
    assert call_count == GENERATION_MAX_ATTEMPTS


async def test_generate_does_not_retry_invalid_prompt(monkeypatch) -> None:
    """Errors that are deterministic w.r.t. inputs should fail fast — no
    point burning quota on retries."""
    gen = _make_gen()

    call_count = 0

    async def fake_once(*, prompt, language, existing_theme_ids):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        raise ThemeGenerationError("invalid_prompt")

    monkeypatch.setattr(gen, "_generate_once", fake_once)
    with pytest.raises(ThemeGenerationError):
        await gen.generate(prompt="x", language="en", existing_theme_ids=set())
    assert call_count == 1
