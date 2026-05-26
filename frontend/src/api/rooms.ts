import { http } from "./http";

export type PlayerId = string;
export type RoomCode = string;
export type Token = string;
export type TeamId = string;
export type RoundId = string;
export type WordId = string;
export type ThemeId = string;
export type RoomState = "lobby" | "board" | "round" | "ended";

export interface CreateRoomResponse {
  code: RoomCode;
  player_id: PlayerId;
  token: Token;
}

export interface JoinRoomResponse {
  code: RoomCode;
  player_id: PlayerId;
  token: Token;
}

export interface PlayerPublic {
  id: PlayerId;
  nickname: string;
  is_host: boolean;
  is_connected: boolean;
  team_id: TeamId | null;
  theme_picks?: ThemeId[];
}

export interface TeamPublic {
  id: TeamId;
  name: string;
  color: string;
  score: number;
  player_ids: PlayerId[];
}

export type TeamMode = "solo" | "teams";
export type RoundMode = "time" | "attempts";

export interface ScoringConfig {
  base_values: number[];
  decay: number;
  penalty_per_attempt: number;
  describer_base_pct: number;
  describer_bonus_pct: number;
}

export interface GameSettings {
  team_mode: TeamMode;
  mode: RoundMode;
  time_seconds: number | null;
  attempts_per_round: number;
  scoring: ScoringConfig;
}

// -------- Game in progress --------

export interface ThemeRef {
  id: ThemeId;
  name: string;
  icon?: string | null;
  /** Player id, if this theme was AI-generated in the room. */
  generated_by?: PlayerId | null;
}

export interface BoardCellRef {
  theme_id: ThemeId;
  difficulty: number;
}

export interface BoardPublic {
  themes: ThemeRef[];
  base_values: number[];
  used: BoardCellRef[];
}

export interface RoundPublic {
  id: RoundId;
  describer_id: PlayerId;
  theme_id: ThemeId;
  difficulty: number;
  base_score: number;
  started_at: string;
  ends_at: string | null;
  state: "active" | "ended";
  live_text?: string;
  reactions?: ReactionState;
  letter_pattern?: string;
  letter_count?: number;
  revealed_indices?: number[];
}

export interface ReactionState {
  likes: PlayerId[];
  dislikes: PlayerId[];
}

export interface DescriberWord {
  word_id: WordId;
  word_text: string;
  hint: string;
}

export interface ScoreboardEntry {
  team_id: TeamId;
  name: string;
  color: string;
  score: number;
}

export interface PerTeamResult {
  team_id: TeamId;
  first_player_id: PlayerId | null;
  correct_at: string | null;
  position: number | null;
  points: number;
  new_score: number;
}

export interface PerPlayerAttempts {
  player_id: PlayerId;
  free_used: number;
  paid_used: number;
  penalty_total: number;
}

export interface RoundResults {
  describer_id: PlayerId;
  describer_team_id: TeamId | null;
  describer_points: number;
  correct_non_describer_team_count: number;
  scored_team_ids: TeamId[];
  per_team: PerTeamResult[];
  per_player_attempts: PerPlayerAttempts[];
}

export interface RoundEndedPayload {
  round_id: RoundId;
  describer_id: PlayerId;
  theme_id: ThemeId;
  difficulty: number;
  base_score: number;
  word_text: string;
  hint: string;
  conceded: boolean;
  forced: boolean;
  results: RoundResults;
}

export interface RoomPublic {
  code: RoomCode;
  state: RoomState;
  host_id: PlayerId | null;
  language?: string;
  players: PlayerPublic[];
  teams: TeamPublic[];
  settings: GameSettings;
  board?: BoardPublic;
  current_round?: RoundPublic;
  current_describer_id?: PlayerId | null;
  describer_queue?: PlayerId[];
  rotation_index?: number;
  corpus_themes?: ThemeRef[];
  max_theme_picks_per_player?: number;
}

export function createRoom(nickname: string, language: string = "en") {
  return http.post<CreateRoomResponse>("/api/rooms", { nickname, language });
}

export function joinRoom(code: RoomCode, nickname: string) {
  return http.post<JoinRoomResponse>(`/api/rooms/${encodeURIComponent(code)}/join`, {
    nickname,
  });
}

export function getRoom(code: RoomCode) {
  return http.get<RoomPublic>(`/api/rooms/${encodeURIComponent(code)}`);
}
