from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
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

    # Translation: real MyMemory client + cache by default. Tests inject
    # their own translator via app.state.translator before the request runs.
    http_client = httpx.AsyncClient(timeout=6.0)
    translator: Translator
    if settings.translator_disabled:
        translator = NoopTranslator()
    else:
        translator = MyMemoryTranslator(
            client=http_client, email=settings.translation_email or None
        )
    app.state.translator = translator
    app.state.translation_cache = TranslationCache()
    app.state._translation_http_client = http_client

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

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {"ok": True, "version": __version__}

    return app


app = create_app()
