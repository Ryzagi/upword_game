"""OpenAI-backed theme generation for the in-lobby word picker.

Given a free-text prompt like "underwater creatures" or "renaissance art" the
generator returns a :class:`Theme` populated with five words — one per
difficulty tier (1..5) — plus a non-spoilery hint for each. The shape matches
the static corpus, so generated themes drop straight into the room's pool
of pickable themes.

The OpenAI call is wrapped in a strict JSON schema so we don't have to parse
free-form text. Validation that mirrors the static-corpus loader runs after
the call: hint must not contain the target, difficulties must each appear,
and the IDs we synthesise are room-unique.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.corpus.loader import _contains_word_phrase, normalise
from app.corpus.schema import Theme, Word

log = logging.getLogger(__name__)

# A theme generated in a 5-player room is short-lived and small — keep the
# round-trip fast so the lobby doesn't feel stuck.
GENERATION_TIMEOUT_SECONDS = 25.0
# How many times to retry when the model returns a payload that fails our
# post-validation (e.g. fewer than 5 words, missing a difficulty tier).
GENERATION_MAX_ATTEMPTS = 3

_THEME_SCHEMA: dict[str, Any] = {
    "name": "generated_theme",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "icon", "words"],
        "properties": {
            "name": {
                "type": "string",
                "description": "Short display name for the theme (1-3 words).",
            },
            "icon": {
                "type": "string",
                "description": (
                    "A single lowercase noun matching the theme (one word, "
                    "ascii, no emoji). Used as a hint to the UI."
                ),
            },
            "words": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["text", "difficulty", "hint"],
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": (
                                "The secret word a player has to guess. "
                                "Lowercase, in the target language, one or "
                                "two words separated by a single space."
                            ),
                        },
                        "difficulty": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": (
                                "1 = very common everyday concept, 5 = "
                                "obscure / requires specialist knowledge."
                            ),
                        },
                        "hint": {
                            "type": "string",
                            "description": (
                                "A 1-sentence clue that gestures at the word "
                                "WITHOUT containing the word itself or any "
                                "obvious morphological variant of it."
                            ),
                        },
                    },
                },
            },
        },
    },
}


class ThemeGenerationError(Exception):
    """Raised when generation fails for any reason — the caller maps this
    to a wire error code visible to the user (`theme_gen_failed`)."""


class ThemeGenerator:
    """Lightweight wrapper around an async OpenAI client. Owns no per-room
    state; safe to share as a singleton on app.state."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        reasoning_effort: str | None = "medium",
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._reasoning_effort = reasoning_effort or None

    async def generate(
        self,
        *,
        prompt: str,
        language: str,
        existing_theme_ids: set[str],
    ) -> Theme:
        """Generate a theme. The returned Theme is guaranteed to be:

        * valid against the corpus schema,
        * unique id-wise relative to ``existing_theme_ids``,
        * have exactly one word per difficulty 1..5,
        * have hints that don't echo the target word.

        Retries up to ``GENERATION_MAX_ATTEMPTS`` times if the model returns
        a payload that fails post-validation (wrong word count, missing
        difficulty tier, or a hint that echoes the target). All other error
        kinds (invalid prompt, upstream failure, timeout) surface immediately.
        """
        last_error: ThemeGenerationError | None = None
        for attempt in range(1, GENERATION_MAX_ATTEMPTS + 1):
            try:
                return await self._generate_once(
                    prompt=prompt,
                    language=language,
                    existing_theme_ids=existing_theme_ids,
                )
            except ThemeGenerationError as e:
                # Only retry on quality issues; everything else is fatal.
                if str(e) != "bad_response":
                    raise
                last_error = e
                log.info(
                    "theme generation attempt %d/%d returned bad_response — retrying",
                    attempt,
                    GENERATION_MAX_ATTEMPTS,
                )
        assert last_error is not None
        raise last_error

    async def _generate_once(
        self,
        *,
        prompt: str,
        language: str,
        existing_theme_ids: set[str],
    ) -> Theme:
        """A single OpenAI call + validation pass. The caller wraps this in
        a retry loop for ``bad_response`` outcomes."""
        clean_prompt = prompt.strip()
        if not clean_prompt or len(clean_prompt) > 120:
            raise ThemeGenerationError("invalid_prompt")

        language_label = _language_label(language)
        system_msg = (
            "You generate themed vocabulary packs for a multiplayer word-"
            "describing party game. Return five distinct words on the "
            "requested theme, exactly one for each difficulty level 1 "
            "through 5. Words and hints MUST be written in "
            f"{language_label}. Each hint must clue the word WITHOUT "
            "containing the word itself or an obvious lemma/stem of it. "
            "Avoid proper nouns unless the theme explicitly calls for "
            "them. Choose family-friendly words only."
        )
        user_msg = f"Theme: {clean_prompt}\nLanguage: {language_label}"

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "response_format": {"type": "json_schema", "json_schema": _THEME_SCHEMA},
        }
        if self._reasoning_effort:
            # Reasoning-class models accept this; others reject. We retry
            # without it on a known error from the SDK.
            kwargs["reasoning_effort"] = self._reasoning_effort

        try:
            completion = await asyncio.wait_for(
                self._client.chat.completions.create(**kwargs),
                timeout=GENERATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as e:
            raise ThemeGenerationError("timeout") from e
        except OpenAIError as e:
            msg = str(e).lower()
            if "reasoning_effort" in msg and self._reasoning_effort is not None:
                # Model doesn't support reasoning_effort — retry without it.
                kwargs.pop("reasoning_effort", None)
                try:
                    completion = await asyncio.wait_for(
                        self._client.chat.completions.create(**kwargs),
                        timeout=GENERATION_TIMEOUT_SECONDS,
                    )
                except (OpenAIError, asyncio.TimeoutError) as e2:
                    log.warning("OpenAI retry failed: %s", e2)
                    raise ThemeGenerationError("upstream") from e2
            else:
                log.warning("OpenAI generation failed: %s", e)
                raise ThemeGenerationError("upstream") from e

        raw = completion.choices[0].message.content or "{}"
        import json
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("OpenAI returned non-JSON: %r", raw[:200])
            raise ThemeGenerationError("bad_response") from e

        return self._build_theme(data, existing_theme_ids)

    def _build_theme(self, data: dict[str, Any], existing_ids: set[str]) -> Theme:
        name = (data.get("name") or "").strip()
        icon = (data.get("icon") or "").strip() or None
        raw_words = data.get("words") or []
        if not name or not isinstance(raw_words, list) or len(raw_words) != 5:
            raise ThemeGenerationError("bad_response")

        difficulties_seen: set[int] = set()
        words: list[Word] = []
        word_ids_seen: set[str] = set()
        for raw in raw_words:
            if not isinstance(raw, dict):
                raise ThemeGenerationError("bad_response")
            text = (raw.get("text") or "").strip()
            hint = (raw.get("hint") or "").strip()
            difficulty = raw.get("difficulty")
            if (
                not text
                or not hint
                or not isinstance(difficulty, int)
                or difficulty < 1
                or difficulty > 5
            ):
                raise ThemeGenerationError("bad_response")
            if _hint_contains_target(hint, text):
                raise ThemeGenerationError("bad_response")
            word_id = _make_word_id(text, word_ids_seen)
            word_ids_seen.add(word_id)
            difficulties_seen.add(difficulty)
            words.append(
                Word(
                    id=word_id,
                    text=text,
                    difficulty=difficulty,
                    hint=hint,
                    aliases=[],
                )
            )
        if difficulties_seen != {1, 2, 3, 4, 5}:
            raise ThemeGenerationError("bad_response")

        theme_id = _make_theme_id(name, existing_ids)
        return Theme(id=theme_id, name=name, icon=icon, words=words)


# --------------------------------------------------------------------- helpers


_LANG_LABELS = {
    "en": "English",
    "ru": "Russian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}


def _language_label(code: str) -> str:
    return _LANG_LABELS.get(code, code)


def _slugify(text: str) -> str:
    """Lowercase, ascii-ish, alnum + hyphen."""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "gen"


def _make_theme_id(name: str, existing_ids: set[str]) -> str:
    base = _slugify(name) or "gen"
    base = f"ai-{base}"
    if base not in existing_ids:
        return base
    # Collision — append a short random suffix.
    for _ in range(6):
        candidate = f"{base}-{secrets.token_hex(2)}"
        if candidate not in existing_ids:
            return candidate
    return f"{base}-{secrets.token_hex(4)}"


def _make_word_id(text: str, seen: set[str]) -> str:
    base = _slugify(text) or "w"
    if base not in seen:
        return base
    for i in range(2, 20):
        candidate = f"{base}-{i}"
        if candidate not in seen:
            return candidate
    return f"{base}-{secrets.token_hex(2)}"


def _hint_contains_target(hint: str, target: str) -> bool:
    """Mirror the static-corpus loader's check so generated themes pass the
    same bar — hints can't echo the target as a word-aligned subsequence."""
    n_hint = normalise(hint)
    n_target = normalise(target)
    if not n_target:
        return True
    return _contains_word_phrase(n_hint, n_target)
