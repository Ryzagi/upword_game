from __future__ import annotations

from typing import Protocol


class TranslationFailureError(Exception):
    """Raised by Translator implementations when the upstream call fails."""

    def __init__(self, reason: str = "upstream_failure") -> None:
        super().__init__(reason)
        self.reason = reason


class Translator(Protocol):
    """A pluggable translation backend.

    Implementations should be idempotent: the API layer relies on caching to
    suppress duplicate upstream calls, but a re-issued translation must
    succeed in the absence of upstream errors.
    """

    async def translate(self, text: str, src: str, dst: str) -> str: ...


class NoopTranslator:
    """Test/fallback translator: echoes the input with the language pair tagged.

    Useful for offline development and CI."""

    async def translate(self, text: str, src: str, dst: str) -> str:
        return f"[{src}>{dst}] {text}"
