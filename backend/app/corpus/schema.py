from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Word(BaseModel):
    id: str
    text: str
    difficulty: int = Field(ge=1, le=5)
    hint: str
    aliases: list[str] = []

    @field_validator("hint")
    @classmethod
    def hint_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("hint must not be empty")
        return v


class Theme(BaseModel):
    id: str
    name: str
    icon: str | None = None
    words: list[Word]


class Corpus(BaseModel):
    version: Literal[1]
    language: str
    themes: list[Theme]
