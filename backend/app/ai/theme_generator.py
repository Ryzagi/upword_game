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
# Max length of the free-text prompt a player can submit. Long enough for
# a descriptive phrase ("space exploration in the 1960s, soviet side") but
# short enough to keep the model focused.
MAX_PROMPT_LENGTH = 400

def _word_schema(difficulty: int) -> dict[str, Any]:
    descriptors = {
        1: "Very easy — a kid would know it. Concrete object or simple action.",
        2: "Easy — clearly recognisable, slightly less concrete.",
        3: "Medium — familiar word but harder to gesture or pantomime.",
        4: "Hard — familiar word that's abstract or relational.",
        5: "Hardest — familiar word that's highly abstract or polysemous.",
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "hint"],
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    f"Difficulty {difficulty} ({descriptors[difficulty]}) — "
                    "the secret word a player has to guess. Lowercase, in "
                    "the target language, one or two words separated by a "
                    "single space."
                ),
            },
            "hint": {
                "type": "string",
                "description": (
                    "A 1-sentence clue that gestures at the word WITHOUT "
                    "containing the word itself or any obvious morphological "
                    "variant of it."
                ),
            },
        },
    }


# The schema has FIVE explicitly-named required fields (word_1..word_5).
# This makes it structurally impossible for the model to skip a difficulty
# level. Previous shape — an unconstrained `words` array of 5 — let the
# model return things like difficulties [1, 1, 3, 4, 5], which our post-
# validator caught but only after burning a retry attempt.
_THEME_SCHEMA: dict[str, Any] = {
    "name": "generated_theme",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "icon", "word_1", "word_2", "word_3", "word_4", "word_5"],
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
            "word_1": _word_schema(1),
            "word_2": _word_schema(2),
            "word_3": _word_schema(3),
            "word_4": _word_schema(4),
            "word_5": _word_schema(5),
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
        exclude_word_ids: list[str] | None = None,
    ) -> Theme:
        """Generate a theme. The returned Theme is guaranteed to be:

        * valid against the corpus schema,
        * unique id-wise relative to ``existing_theme_ids``,
        * have exactly one word per difficulty 1..5,
        * have hints that don't echo the target word.

        ``exclude_word_ids`` is a soft hint (used when re-rolling a theme) —
        the slugified previous words are mentioned in the prompt so the model
        tries to avoid repeating them. It's not a hard guarantee.

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
                    exclude_word_ids=exclude_word_ids,
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
        exclude_word_ids: list[str] | None = None,
    ) -> Theme:
        """A single OpenAI call + validation pass. The caller wraps this in
        a retry loop for ``bad_response`` outcomes."""
        clean_prompt = prompt.strip()
        if not clean_prompt or len(clean_prompt) > MAX_PROMPT_LENGTH:
            raise ThemeGenerationError("invalid_prompt")

        language_label = _language_label(language)
        system_msg = (
            "You generate themed vocabulary packs for a multiplayer word-"
            "describing party game played by ADULT friend groups. Return "
            "exactly five distinct, COMMON everyday words on the requested "
            "theme — one per difficulty level 1..5.\n"
            "\n"
            "All words must be familiar to a typical adult. Difficulty "
            "captures how HARD THE WORD IS TO DESCRIBE without saying it, "
            "not how rare or specialist it is. Use this scale:\n"
            "  1 = a kid would know it (concrete object or simple action)\n"
            "  2 = clearly recognisable, slightly less concrete\n"
            "  3 = familiar word but harder to gesture or pantomime\n"
            "  4 = familiar word that's abstract or relational (a concept, "
            "an emotion, a process)\n"
            "  5 = familiar word that is highly abstract or has many "
            "overlapping meanings — still everyday vocabulary, NOT jargon\n"
            "\n"
            "DO NOT pick obscure scientific, medical, legal, or technical "
            "terms. If your candidate would make an average player say "
            "\"I've never heard of that,\" choose something simpler.\n"
            "\n"
            "CONTENT POLICY: this is an adult game. If the player's prompt "
            "calls for mature themes — alcohol, swearing, sex, drugs, "
            "dark humour, etc. — generate them honestly without softening "
            "them into euphemisms. Treat the requested topic as the "
            "ground truth. The only hard limits are: no slurs targeting "
            "protected groups, no sexual content involving minors, no "
            "real-world instructions for violence or self-harm.\n"
            f"\nWords and hints MUST be written in {language_label}. Each "
            "hint must clue the word WITHOUT containing the word itself or "
            "an obvious lemma/stem of it. Avoid proper nouns unless the "
            "theme explicitly calls for them."
        )
        user_msg = f"Theme: {clean_prompt}\nLanguage: {language_label}"
        if exclude_word_ids:
            # Soft avoidance for re-rolls: the ids are slugs of prior words.
            avoid = ", ".join(
                w.replace("-", " ") for w in exclude_word_ids if isinstance(w, str)
            )[:300]
            if avoid:
                user_msg += (
                    f"\nThis is a re-roll. Pick DIFFERENT words than these "
                    f"(do not reuse them): {avoid}"
                )

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
        if not name:
            raise ThemeGenerationError("bad_response")

        # New shape: one named field per difficulty. Falls back to the legacy
        # `words: [...]` shape if the model happens to return that — keeps
        # us forward-compatible while the schema rollout settles.
        per_difficulty = self._extract_words_per_difficulty(data)
        if per_difficulty is None:
            raise ThemeGenerationError("bad_response")

        words: list[Word] = []
        word_ids_seen: set[str] = set()
        for difficulty in (1, 2, 3, 4, 5):
            entry = per_difficulty.get(difficulty)
            if not isinstance(entry, dict):
                raise ThemeGenerationError("bad_response")
            text = (entry.get("text") or "").strip()
            hint = (entry.get("hint") or "").strip()
            if not text or not hint:
                raise ThemeGenerationError("bad_response")
            if _hint_contains_target(hint, text):
                raise ThemeGenerationError("bad_response")
            word_id = _make_word_id(text, word_ids_seen)
            word_ids_seen.add(word_id)
            words.append(
                Word(
                    id=word_id,
                    text=text,
                    difficulty=difficulty,
                    hint=hint,
                    aliases=[],
                )
            )

        theme_id = _make_theme_id(name, existing_ids)
        return Theme(id=theme_id, name=name, icon=icon, words=words)

    @staticmethod
    def _extract_words_per_difficulty(
        data: dict[str, Any],
    ) -> dict[int, dict[str, Any]] | None:
        """Pull the five words out of the response. Accepts the new shape
        (``word_1``..``word_5`` keys) and the legacy shape (``words`` array
        with explicit ``difficulty`` fields). Returns None if neither shape
        yields exactly five entries covering difficulties 1..5.
        """
        out: dict[int, dict[str, Any]] = {}

        # Preferred: named fields.
        for difficulty in range(1, 6):
            entry = data.get(f"word_{difficulty}")
            if isinstance(entry, dict):
                out[difficulty] = entry
        if len(out) == 5:
            return out

        # Legacy fallback: array with explicit difficulty per item.
        raw_words = data.get("words")
        if isinstance(raw_words, list) and len(raw_words) == 5:
            seen: dict[int, dict[str, Any]] = {}
            for raw in raw_words:
                if not isinstance(raw, dict):
                    return None
                d = raw.get("difficulty")
                if not isinstance(d, int) or d < 1 or d > 5:
                    return None
                # Duplicate difficulty? Fail this shape and bail.
                if d in seen:
                    return None
                seen[d] = raw
            if set(seen.keys()) == {1, 2, 3, 4, 5}:
                return seen

        return None


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
