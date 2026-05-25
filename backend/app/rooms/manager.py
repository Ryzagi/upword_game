from __future__ import annotations

import asyncio
import logging

from app.corpus.schema import Corpus
from app.models.errors import LanguageUnsupportedError, RoomNotFoundError
from app.models.player import Player
from app.rooms.codes import generate_room_code
from app.rooms.room import Room

log = logging.getLogger(__name__)

MAX_ROOMS = 10_000
MAX_CODE_GENERATION_ATTEMPTS = 8


class RoomManager:
    """In-process room registry. One instance per process, attached to app state."""

    def __init__(self, corpora: dict[str, Corpus] | None = None) -> None:
        self._rooms: dict[str, Room] = {}
        self._corpora: dict[str, Corpus] = corpora or {}
        self._lock = asyncio.Lock()

    # ----------------------------------------------------------------- create

    async def create_room(
        self, host_nickname: str, language: str = "en"
    ) -> tuple[Room, Player, str]:
        corpus = self._corpora.get(language)
        if corpus is None:
            raise LanguageUnsupportedError()
        async with self._lock:
            if len(self._rooms) >= MAX_ROOMS:
                raise RuntimeError("max_rooms_reached")
            code = self._gen_unique_code_locked()
            room = Room(code, corpus=corpus)
            self._rooms[code] = room
        player, token = await room.add_player(host_nickname)
        return room, player, token

    def _gen_unique_code_locked(self) -> str:
        for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
            code = generate_room_code()
            if code not in self._rooms:
                return code
        raise RuntimeError("could_not_generate_unique_code")

    # ------------------------------------------------------------------- get

    def get_room(self, code: str) -> Room | None:
        return self._rooms.get(code.upper())

    def require_room(self, code: str) -> Room:
        room = self.get_room(code)
        if room is None:
            raise RoomNotFoundError()
        return room

    # ----------------------------------------------------------------- join

    async def join_room(self, code: str, nickname: str) -> tuple[Room, Player, str]:
        room = self.require_room(code)
        player, token = await room.add_player(nickname)
        return room, player, token

    # ------------------------------------------------------------- drop room

    async def drop_room_if_empty(self, code: str) -> bool:
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return False
            if room.is_empty():
                self._rooms.pop(code, None)
                return True
            return False

    # ------------------------------------------------------------- testing

    def all_rooms(self) -> list[Room]:
        return list(self._rooms.values())
