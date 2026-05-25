from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.corpus.loader import normalise
from app.translation.base import TranslationFailureError, Translator
from app.translation.cache import TranslationCache

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    src: str = Field(min_length=2, max_length=12)
    dst: str = Field(min_length=2, max_length=12)


class TranslateResponse(BaseModel):
    translated: str
    provider: str


@router.post("", response_model=TranslateResponse)
async def translate(request: Request, body: TranslateRequest) -> TranslateResponse:
    if body.src == body.dst:
        # Silly but cheap: same-language pair returns the input unchanged.
        return TranslateResponse(translated=body.text, provider="passthrough")

    translator: Translator | None = getattr(request.app.state, "translator", None)
    if translator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "translation_unavailable"}},
        )

    cache: TranslationCache | None = getattr(request.app.state, "translation_cache", None)
    key = (body.src, body.dst, normalise(body.text))
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            return TranslateResponse(translated=cached, provider="cache")

    try:
        translated = await translator.translate(body.text, body.src, body.dst)
    except TranslationFailureError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": e.reason}},
        ) from e

    if cache is not None:
        cache.set(key, translated)
    return TranslateResponse(
        translated=translated,
        provider=type(translator).__name__,
    )
