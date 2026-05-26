"""OpenAI-backed translator. Calls the chat completions endpoint with a
strict, low-creativity instruction so the model returns only the
translated text — no explanation, no preface, no quotes.

We use a small/fast model by default (`gpt-5.4-nano-2026-03-17`) and a
short timeout. The Translator protocol just returns a string; upstream
errors raise :class:`TranslationFailureError`.
"""

from __future__ import annotations

import asyncio
import logging

from openai import AsyncOpenAI, OpenAIError

from app.translation.base import TranslationFailureError

log = logging.getLogger(__name__)

TRANSLATION_TIMEOUT_SECONDS = 12.0

_LANG_LABELS = {
    "en": "English",
    "ru": "Russian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}


def _label(code: str) -> str:
    return _LANG_LABELS.get(code, code)


class OpenAITranslator:
    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OpenAI API key required for OpenAITranslator")
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def translate(self, text: str, src: str, dst: str) -> str:
        src_label = _label(src)
        dst_label = _label(dst)
        system = (
            f"You translate text from {src_label} to {dst_label}. "
            "Return ONLY the translated text with no preface, quotes, "
            "notes, or explanation. Preserve punctuation. If the input "
            "is a single word, return a single word."
        )
        try:
            completion = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": text},
                    ],
                    temperature=0,
                ),
                timeout=TRANSLATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as e:
            log.warning("OpenAI translation timeout for %s→%s", src, dst)
            raise TranslationFailureError("upstream_failure") from e
        except OpenAIError as e:
            log.warning("OpenAI translation failed: %s", e)
            raise TranslationFailureError("upstream_failure") from e

        content = (completion.choices[0].message.content or "").strip()
        # Defensive: strip wrapping quotes that some models add anyway.
        if len(content) >= 2 and content[0] == content[-1] and content[0] in ('"', "'", "«"):
            content = content[1:-1].strip()
        if not content:
            raise TranslationFailureError("upstream_failure")
        return content
