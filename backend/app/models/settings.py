from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ScoringConfig(BaseModel):
    base_values: list[int] = Field(default_factory=lambda: [100, 200, 300, 400, 500])
    decay: float = 0.8
    penalty_per_attempt: int = 10
    describer_base_pct: float = 0.5
    describer_bonus_pct: float = 0.1


TeamMode = Literal["solo", "teams"]
RoundMode = Literal["time", "attempts"]
ALLOWED_TIME_SECONDS = {30, 60, 90, 120}


class GameSettings(BaseModel):
    team_mode: TeamMode = "solo"
    mode: RoundMode = "attempts"
    # null means "unlimited" in time mode; ignored in attempts mode.
    time_seconds: int | None = 60
    # Positive int; ignored in time mode.
    attempts_per_round: int = 5
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)

    @model_validator(mode="after")
    def _check(self) -> "GameSettings":
        if self.mode == "time":
            if self.time_seconds is not None and self.time_seconds not in ALLOWED_TIME_SECONDS:
                raise ValueError("bad_settings")
        else:
            if self.attempts_per_round < 1 or self.attempts_per_round > 50:
                raise ValueError("bad_settings")
        return self
