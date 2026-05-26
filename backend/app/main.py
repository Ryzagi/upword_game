from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.ai.theme_generator import ThemeGenerator
from app.api.corpus import router as corpus_router
from app.api.rooms import router as rooms_router
from app.api.translate import router as translate_router
from app.config import get_settings
from app.corpus.loader import load_all_corpora
from app.rooms.manager import RoomManager
from app.translation.base import NoopTranslator, Translator
from app.translation.cache import TranslationCache
from app.translation.mymemory import MyMemoryTranslator
from app.ws.router import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.corpora = load_all_corpora(settings.corpus_dir)
    app.state.room_manager = RoomManager(corpora=app.state.corpora)

    # Translation backend.
    #   * Tests / explicit disable → NoopTranslator (echoes input)
    #   * OPENAI_API_KEY set → OpenAITranslator (preferred — better quality
    #     and no daily quota)
    #   * Otherwise → MyMemoryTranslator (free, daily-quota-limited)
    http_client = httpx.AsyncClient(timeout=6.0)
    translator: Translator
    if settings.translator_disabled:
        translator = NoopTranslator()
    elif settings.openai_api_key:
        from app.translation.openai import OpenAITranslator

        translator = OpenAITranslator(
            api_key=settings.openai_api_key,
            model=settings.openai_translation_model,
        )
    else:
        translator = MyMemoryTranslator(
            client=http_client, email=settings.translation_email or None
        )
    app.state.translator = translator
    app.state.translation_cache = TranslationCache()
    app.state._translation_http_client = http_client

    # AI theme generator — only enabled if a key is configured. Otherwise
    # the WS handler short-circuits with theme_gen_unavailable.
    if settings.openai_api_key:
        app.state.theme_generator = ThemeGenerator(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            reasoning_effort=settings.openai_reasoning_effort,
        )
    else:
        app.state.theme_generator = None

    try:
        yield
    finally:
        await http_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Word Describer", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(corpus_router, prefix="/api/corpus", tags=["corpus"])
    app.include_router(rooms_router, prefix="/api/rooms", tags=["rooms"])
    app.include_router(translate_router, prefix="/api/translate", tags=["translate"])
    app.include_router(ws_router, prefix="/ws")

    # Static music directory (background-music.mp3 etc.). Mounted only when
    # the directory exists so dev environments without media files still boot.
    music_dir = settings.corpus_dir / "music"
    if music_dir.is_dir():
        app.mount(
            "/api/music",
            StaticFiles(directory=music_dir),
            name="music",
        )

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {"ok": True, "version": __version__}

    return app


app = create_app()
