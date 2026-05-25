from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.models.errors import DomainError, NicknameInvalidError
from app.rooms.manager import RoomManager

router = APIRouter()


class CreateRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)
    language: str = "en"


class CreateRoomResponse(BaseModel):
    code: str
    player_id: str
    token: str


class JoinRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)


class JoinRoomResponse(BaseModel):
    player_id: str
    token: str
    code: str


def _manager(request: Request) -> RoomManager:
    return request.app.state.room_manager  # type: ignore[no-any-return]


def _domain_error(exc: DomainError | ValueError) -> HTTPException:
    code = exc.code if isinstance(exc, DomainError) else str(exc)
    http_status = (
        status.HTTP_404_NOT_FOUND
        if code == "room_not_found"
        else status.HTTP_409_CONFLICT
        if code in {"nickname_taken", "room_full"}
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=http_status, detail={"error": {"code": code}})


@router.post("", response_model=CreateRoomResponse)
async def create_room(request: Request, body: CreateRoomRequest) -> CreateRoomResponse:
    try:
        room, player, token = await _manager(request).create_room(
            body.nickname, language=body.language
        )
    except ValueError as e:
        raise _domain_error(NicknameInvalidError(str(e))) from e
    except DomainError as e:
        raise _domain_error(e) from e
    return CreateRoomResponse(code=room.code, player_id=player.id, token=token)


@router.post("/{code}/join", response_model=JoinRoomResponse)
async def join_room(request: Request, code: str, body: JoinRoomRequest) -> JoinRoomResponse:
    try:
        room, player, token = await _manager(request).join_room(code, body.nickname)
    except ValueError as e:
        raise _domain_error(NicknameInvalidError(str(e))) from e
    except DomainError as e:
        raise _domain_error(e) from e
    return JoinRoomResponse(player_id=player.id, token=token, code=room.code)


@router.get("/{code}")
async def get_room(request: Request, code: str) -> dict[str, object]:
    try:
        room = _manager(request).require_room(code)
    except DomainError as e:
        raise _domain_error(e) from e
    return room.snapshot()
