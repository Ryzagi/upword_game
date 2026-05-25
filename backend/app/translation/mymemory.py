from __future__ import annotations

import logging

import httpx

from app.translation.base import TranslationFailureError

log = logging.getLogger(__name__)

MYMEMORY_URL = "https://api.mymemory.translated.net/get"


class MyMemoryTranslator:
    """Translator backed by the free MyMemory API.

    The `email` parameter (passed as `de`) lifts the daily free quota from
    1k to 10k characters; supply it via app settings in production.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        email: str | None = None,
        timeout: float = 6.0,
    ) -> None:
        self._client = client
        self._email = email
        self._timeout = timeout

    async def translate(self, text: str, src: str, dst: str) -> str:
        params: dict[str, str] = {"q": text, "langpair": f"{src}|{dst}"}
        if self._email:
            params["de"] = self._email
        try:
            response = await self._client.get(MYMEMORY_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            log.warning("translation upstream error: %r", e)
            raise TranslationFailureError("upstream_failure") from e
        except ValueError as e:  # bad json
            log.warning("translation upstream returned bad json: %r", e)
            raise TranslationFailureError("upstream_failure") from e

        translated = (
            data.get("responseData", {}).get("translatedText") if isinstance(data, dict) else None
        )
        if not isinstance(translated, str) or not translated:
            raise TranslationFailureError("upstream_failure")
        return translated
