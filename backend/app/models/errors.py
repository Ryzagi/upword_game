"""Domain-level errors. The `code` is the stable wire identifier the client uses
to look up a localised message."""


class DomainError(Exception):
    """Base for all server-defined room/game errors.

    The error message is the wire `code`; instances carry no user-visible text.
    """

    code: str

    def __init__(self, code: str | None = None) -> None:
        resolved = code or getattr(self, "code", None) or "internal_error"
        self.code = resolved
        super().__init__(resolved)


class RoomNotFoundError(DomainError):
    code = "room_not_found"


class RoomFullError(DomainError):
    code = "room_full"


class NicknameTakenError(DomainError):
    code = "nickname_taken"


class NicknameInvalidError(DomainError):
    code = "nickname_invalid"


class InvalidTokenError(DomainError):
    code = "invalid_token"


class NotHostError(DomainError):
    code = "not_host"


class InvalidPayloadError(DomainError):
    code = "invalid_payload"


class TeamNotFoundError(DomainError):
    code = "team_not_found"


class TeamNameTakenError(DomainError):
    code = "team_name_taken"


class TeamLimitExceededError(DomainError):
    code = "team_limit_exceeded"


class BadSettingsError(DomainError):
    code = "bad_settings"


class NotDescriberError(DomainError):
    code = "not_describer"


class NotEnoughPlayersError(DomainError):
    code = "not_enough_players"


class BadTeamConfigError(DomainError):
    code = "bad_team_config"


class CellAlreadyUsedError(DomainError):
    code = "cell_already_used"


class UnknownThemeError(DomainError):
    code = "unknown_theme"


class NoWordsAvailableError(DomainError):
    code = "no_words_available"


class RoomNotInLobbyError(DomainError):
    code = "room_not_in_lobby"


class RoomNotOnBoardError(DomainError):
    code = "room_not_on_board"


class RoundNotActiveError(DomainError):
    code = "round_not_active"


class GameNotEndedError(DomainError):
    code = "game_not_ended"


class LanguageUnsupportedError(DomainError):
    code = "language_unsupported"


class AlreadyGuessedCorrectlyError(DomainError):
    code = "already_guessed_correctly"


class DescriberCannotGuessError(DomainError):
    code = "describer_cannot_guess"


class BadThemePicksError(DomainError):
    code = "bad_theme_picks"


class ThemeGenRateLimitedError(DomainError):
    code = "theme_gen_rate_limited"


class ThemeGenCapReachedError(DomainError):
    code = "theme_gen_cap_reached"


class ThemeGenFailedError(DomainError):
    code = "theme_gen_failed"


class ThemeGenInvalidPromptError(DomainError):
    code = "theme_gen_invalid_prompt"


class ThemeGenUnavailableError(DomainError):
    code = "theme_gen_unavailable"
