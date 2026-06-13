import type {
  BoardPublic,
  DescriberWord,
  GameSettings,
  PlayerId,
  PlayerPublic,
  RoomCode,
  RoomPublic,
  RoundEndedPayload,
  RoundPublic,
  ScoreboardEntry,
  TeamId,
  TeamPublic,
  ThemeId,
  ThemeRef,
} from "../api/rooms";

// ----- Server → Client -----

export interface YourRoundState {
  free_attempts_left: number | null;
  paid_attempts_total: number;
  you_have_guessed_correctly: boolean;
}

export interface RoomSnapshotEvent {
  type: "room/snapshot";
  data: RoomPublic & {
    your_player_id: PlayerId;
    your_describer_word?: DescriberWord;
    your_round_state?: YourRoundState;
  };
}

export interface LobbyStateEvent {
  type: "lobby/state";
  data: {
    host_id: PlayerId | null;
    players: PlayerPublic[];
    teams: TeamPublic[];
    settings: GameSettings;
    state?: "lobby" | "board" | "round" | "ended";
    max_theme_picks_per_player?: number;
    theme_gen_used?: Record<string, number>;
    corpus_themes?: ThemeRef[];
  };
}

export interface LobbyPlayerJoinedEvent {
  type: "lobby/player_joined";
  data: { player: PlayerPublic };
}

export interface LobbyPlayerLeftEvent {
  type: "lobby/player_left";
  data: { player_id: PlayerId };
}

export interface GameStartedEvent {
  type: "game/started";
  data: {
    board: BoardPublic;
    scoreboard: ScoreboardEntry[];
    describer_queue: PlayerId[];
    current_describer_id: PlayerId | null;
  };
}

export interface BoardStateEvent {
  type: "board/state";
  data: {
    board: BoardPublic;
    scoreboard: ScoreboardEntry[];
    current_describer_id: PlayerId | null;
  };
}

export interface RoundStartedEvent {
  type: "round/started";
  data: RoundPublic;
}

export interface DescriberWordEvent {
  type: "describer/word";
  data: DescriberWord;
}

export interface RoundEndedEvent {
  type: "round/ended";
  data: RoundEndedPayload;
}

export interface GameEndedEvent {
  type: "game/ended";
  data: { final_scores: ScoreboardEntry[] };
}

export interface DescriberTextEvent {
  type: "describer/text";
  data: { text: string };
}

export interface GuessCorrectEvent {
  type: "guess/correct";
  data: {
    player_id: PlayerId;
    team_id: TeamId;
    position: number;
    points_awarded: number;
    total_team_score: number;
  };
}

export interface GuessWrongEvent {
  type: "guess/wrong";
  data: {
    free_attempts_left: number | null;
    paid_attempts_total: number;
  };
}

export interface GuessPenaltyEvent {
  type: "guess/penalty";
  data: {
    amount: number;
    new_balance: number;
  };
}

export interface GuessFeedEvent {
  type: "guess/feed";
  data: {
    player_id: PlayerId;
    team_id: TeamId | null;
    text: string;
    correct: boolean;
    at: string;
  };
}

export interface ReactionStateEvent {
  type: "reaction/state";
  data: {
    likes: PlayerId[];
    dislikes: PlayerId[];
  };
}

export interface RoundLetterRevealEvent {
  type: "round/letter_reveal";
  data: {
    revealed_indices: number[];
    pattern: string;
  };
}

export interface RoundConcedeStateEvent {
  type: "round/concede_state";
  data: {
    player_id: PlayerId;
    conceded_player_ids: PlayerId[];
  };
}

export interface LobbyThemeAddedEvent {
  type: "lobby/theme_added";
  data: {
    theme: ThemeRef;
    corpus_themes: ThemeRef[];
    theme_gen_used?: Record<string, number>;
  };
}

export interface LobbyThemeRegeneratedEvent {
  type: "lobby/theme_regenerated";
  data: {
    theme_id: ThemeId;
    corpus_themes: ThemeRef[];
  };
}

export interface ServerPingEvent {
  type: "server/ping";
  data?: undefined;
}

export interface ServerErrorEvent {
  type: "error";
  data: { code: string; ref?: string };
}

export type ServerEvent =
  | RoomSnapshotEvent
  | LobbyStateEvent
  | LobbyPlayerJoinedEvent
  | LobbyPlayerLeftEvent
  | GameStartedEvent
  | BoardStateEvent
  | RoundStartedEvent
  | DescriberWordEvent
  | DescriberTextEvent
  | GuessCorrectEvent
  | GuessWrongEvent
  | GuessPenaltyEvent
  | GuessFeedEvent
  | ReactionStateEvent
  | RoundLetterRevealEvent
  | RoundConcedeStateEvent
  | LobbyThemeAddedEvent
  | LobbyThemeRegeneratedEvent
  | RoundEndedEvent
  | GameEndedEvent
  | ServerPingEvent
  | ServerErrorEvent;

// ----- Client → Server -----

export interface LobbyRenameEvent {
  type: "lobby/rename";
  data: { nickname: string };
}

export interface LobbyTeamCreateEvent {
  type: "lobby/team_create";
  data: { name: string };
}

export interface LobbyTeamDeleteEvent {
  type: "lobby/team_delete";
  data: { team_id: TeamId };
}

export interface LobbyTeamRenameEvent {
  type: "lobby/team_rename";
  data: { team_id: TeamId; name: string };
}

export interface LobbyTeamSetEvent {
  type: "lobby/team_set";
  data: { player_id: PlayerId; team_id: TeamId | null };
}

export interface LobbyRandomizeTeamsEvent {
  type: "lobby/randomize_teams";
  data: { team_count: number };
}

export interface LobbySettingsSetEvent {
  type: "lobby/settings_set";
  data: Partial<GameSettings>;
}

export interface LobbyStartGameEvent {
  type: "lobby/start_game";
  data?: Record<string, never>;
}

export interface LobbyThemePicksSetEvent {
  type: "lobby/theme_picks_set";
  data: { theme_ids: ThemeId[] };
}

export interface LobbyThemeGenerateEvent {
  type: "lobby/theme_generate";
  data: { prompt: string };
}

export interface LobbyThemeDeleteEvent {
  type: "lobby/theme_delete";
  data: { theme_id: ThemeId };
}

export interface LobbyThemeRegenerateEvent {
  type: "lobby/theme_regenerate";
  data: { theme_id: ThemeId };
}

export interface RoundPickCellEvent {
  type: "round/pick_cell";
  data: { theme_id: ThemeId; difficulty: number };
}

export interface RoundConcedeEvent {
  type: "round/concede";
  data?: Record<string, never>;
}

export interface RoundForceEndEvent {
  type: "round/force_end";
  data?: Record<string, never>;
}

export interface GamePlayAgainEvent {
  type: "game/play_again";
  data?: Record<string, never>;
}

export interface DescriberTextOutEvent {
  type: "describer/text";
  data: { text: string };
}

export interface GuessSubmitEvent {
  type: "guess/submit";
  data: { text: string };
}

export interface ReactionToggleEvent {
  type: "reaction/toggle";
  data: { kind: "like" | "dislike" };
}

export interface ClientPongEvent {
  type: "client/pong";
  data?: undefined;
}

export type ClientEvent =
  | LobbyRenameEvent
  | LobbyTeamCreateEvent
  | LobbyTeamDeleteEvent
  | LobbyTeamRenameEvent
  | LobbyTeamSetEvent
  | LobbyRandomizeTeamsEvent
  | LobbySettingsSetEvent
  | LobbyStartGameEvent
  | LobbyThemePicksSetEvent
  | LobbyThemeGenerateEvent
  | LobbyThemeDeleteEvent
  | LobbyThemeRegenerateEvent
  | RoundPickCellEvent
  | RoundConcedeEvent
  | RoundForceEndEvent
  | GamePlayAgainEvent
  | DescriberTextOutEvent
  | GuessSubmitEvent
  | ReactionToggleEvent
  | ClientPongEvent;

export const CONNECTION_CLOSE_CODES = {
  ROOM_NOT_FOUND: 4404,
  INVALID_TOKEN: 4401,
  IDLE_TIMEOUT: 4408,
  REPLACED: 4000,
} as const;

export function wsUrl(code: RoomCode, token: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/rooms/${encodeURIComponent(code)}?token=${encodeURIComponent(
    token
  )}`;
}
