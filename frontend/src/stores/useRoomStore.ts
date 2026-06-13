import { create } from "zustand";

import type {
  BoardPublic,
  DescriberWord,
  GameSettings,
  PlayerId,
  PlayerPublic,
  ReactionState,
  RoomCode,
  RoomState,
  RoundEndedPayload,
  RoundPublic,
  ScoreboardEntry,
  TeamId,
  TeamPublic,
  ThemeRef,
} from "../api/rooms";
import type { ServerEvent } from "../ws/events";

const DEFAULT_SCORING = {
  base_values: [100, 200, 300, 400, 500],
  decay: 0.8,
  penalty_per_attempt: 10,
  describer_base_pct: 0.5,
  describer_bonus_pct: 0.1,
};

const DEFAULT_SETTINGS: GameSettings = {
  team_mode: "solo",
  mode: "attempts",
  time_seconds: 60,
  attempts_per_round: 5,
  scoring: DEFAULT_SCORING,
};

/** A transient flash for the current player's own guess feedback. */
export interface GuessFlash {
  kind: "correct" | "wrong" | "penalty";
  message?: string;
  free_attempts_left?: number | null;
  paid_attempts_total?: number;
  amount?: number;
}

export interface ChatMessage {
  id: string;          // synthesised: at + player_id
  player_id: PlayerId;
  team_id: TeamId | null;
  text: string;
  correct: boolean;
  at: string;
}

const MAX_CHAT_HISTORY = 80;

interface RoomStoreState {
  // ---- Lobby state ----
  code: RoomCode | null;
  state: RoomState;
  hostId: PlayerId | null;
  yourPlayerId: PlayerId | null;
  /** Corpus language for this room (the language the WORDS are in). Set at
   *  room creation and frozen for the room's lifetime. Separate from each
   *  player's UI language. */
  roomLanguage: string;
  players: PlayerPublic[];
  teams: TeamPublic[];
  settings: GameSettings;

  // ---- Game-in-progress state ----
  board: BoardPublic | null;
  currentRound: RoundPublic | null;
  currentDescriberId: PlayerId | null;
  describerQueue: PlayerId[];
  /** Describer-only word for the active round. */
  describerWord: DescriberWord | null;
  /** The describer's live-typed description, replicated to everyone. */
  liveText: string;
  /** Your own attempt budget for the current round (attempts mode). */
  yourFreeAttemptsLeft: number | null;
  yourPaidAttemptsTotal: number;
  /** Players (any team) who've already guessed correctly this round. */
  correctPlayerIds: PlayerId[];
  /** Aggregate like/dislike state for the active round. */
  reactions: ReactionState;
  /** Per-round chat-style feed of every (non-empty) guess. */
  chatFeed: ChatMessage[];
  /** Result payload from the most recent round/ended — used for the summary modal. */
  lastRoundResults: RoundEndedPayload | null;
  /** Final scoreboard from game/ended. */
  finalScores: ScoreboardEntry[] | null;
  /** Latest guess feedback flash for the current player. */
  guessFlash: GuessFlash | null;

  // ---- Lobby theme picker ----
  corpusThemes: ThemeRef[];
  maxThemePicksPerPlayer: number;
  /** Per-player count of AI themes generated this lobby session
   *  (player_id -> count). Resets when the room returns to the lobby. */
  themeGenUsed: Record<string, number>;

  // ---- Errors ----
  lastError: { code: string; ref?: string } | null;

  applyServerEvent: (event: ServerEvent) => void;
  reset: () => void;
  clearError: () => void;
  clearGuessFlash: () => void;
  acknowledgeRoundResult: () => void;
}

const empty: Omit<
  RoomStoreState,
  | "applyServerEvent"
  | "reset"
  | "clearError"
  | "clearGuessFlash"
  | "acknowledgeRoundResult"
> = {
  code: null,
  state: "lobby",
  hostId: null,
  yourPlayerId: null,
  roomLanguage: "en",
  players: [],
  teams: [],
  settings: DEFAULT_SETTINGS,
  board: null,
  currentRound: null,
  currentDescriberId: null,
  describerQueue: [],
  describerWord: null,
  liveText: "",
  yourFreeAttemptsLeft: null,
  yourPaidAttemptsTotal: 0,
  correctPlayerIds: [],
  reactions: { likes: [], dislikes: [] },
  chatFeed: [],
  lastRoundResults: null,
  finalScores: null,
  guessFlash: null,
  corpusThemes: [],
  maxThemePicksPerPlayer: 1,
  themeGenUsed: {},
  lastError: null,
};

function clearRoundEphemerals(): Partial<RoomStoreState> {
  return {
    liveText: "",
    yourFreeAttemptsLeft: null,
    yourPaidAttemptsTotal: 0,
    correctPlayerIds: [],
    reactions: { likes: [], dislikes: [] },
    chatFeed: [],
    guessFlash: null,
  };
}

export const useRoomStore = create<RoomStoreState>((set) => ({
  ...empty,

  applyServerEvent: (event) =>
    set((current) => {
      switch (event.type) {
        case "room/snapshot": {
          const d = event.data;
          return {
            code: d.code,
            state: d.state,
            hostId: d.host_id,
            roomLanguage: d.language ?? "en",
            yourPlayerId: d.your_player_id,
            players: d.players,
            teams: d.teams,
            settings: d.settings,
            board: d.board ?? null,
            currentRound: d.current_round ?? null,
            currentDescriberId: d.current_describer_id ?? null,
            describerQueue: d.describer_queue ?? [],
            describerWord: d.your_describer_word ?? null,
            liveText: d.current_round?.live_text ?? "",
            yourFreeAttemptsLeft:
              d.your_round_state?.free_attempts_left ??
              (d.settings.mode === "attempts"
                ? d.settings.attempts_per_round
                : null),
            yourPaidAttemptsTotal: d.your_round_state?.paid_attempts_total ?? 0,
            correctPlayerIds: d.your_round_state?.you_have_guessed_correctly
              ? [d.your_player_id]
              : [],
            reactions: d.current_round?.reactions ?? { likes: [], dislikes: [] },
            chatFeed: [],
            lastRoundResults: null,
            finalScores: null,
            guessFlash: null,
            corpusThemes: d.corpus_themes ?? [],
            maxThemePicksPerPlayer: d.max_theme_picks_per_player ?? 1,
            themeGenUsed: d.theme_gen_used ?? {},
            lastError: null,
          };
        }
        case "lobby/state": {
          const patch: Partial<RoomStoreState> = {
            hostId: event.data.host_id,
            players: event.data.players,
            teams: event.data.teams,
            settings: event.data.settings,
          };
          if (event.data.state !== undefined) {
            patch.state = event.data.state;
          }
          if (event.data.max_theme_picks_per_player !== undefined) {
            patch.maxThemePicksPerPlayer = event.data.max_theme_picks_per_player;
          }
          if (event.data.theme_gen_used !== undefined) {
            patch.themeGenUsed = event.data.theme_gen_used;
          }
          if (event.data.corpus_themes !== undefined) {
            patch.corpusThemes = event.data.corpus_themes;
          }
          return patch;
        }
        case "lobby/player_joined": {
          const existing = current.players.find((p) => p.id === event.data.player.id);
          if (existing) return {};
          return { players: [...current.players, event.data.player] };
        }
        case "lobby/player_left":
          return {
            players: current.players.filter((p) => p.id !== event.data.player_id),
          };
        case "game/started":
          return {
            state: "board",
            board: event.data.board,
            currentRound: null,
            currentDescriberId: event.data.current_describer_id,
            describerQueue: event.data.describer_queue,
            describerWord: null,
            lastRoundResults: null,
            finalScores: null,
            // Once the game starts, any leftover lobby-only error
            // (bad_team_config, not_enough_players, bad_theme_picks…) is
            // stale and would just confuse players. Drop it.
            lastError: null,
            ...clearRoundEphemerals(),
          };
        case "round/started":
          return {
            state: "round",
            currentRound: event.data,
            currentDescriberId: event.data.describer_id,
            lastRoundResults: null,
            lastError: null,
            ...clearRoundEphemerals(),
            // Reset your attempt budget from settings (attempts mode only).
            yourFreeAttemptsLeft:
              current.settings.mode === "attempts"
                ? current.settings.attempts_per_round
                : null,
            yourPaidAttemptsTotal: 0,
          };
        case "describer/word":
          return { describerWord: event.data };
        case "describer/text":
          return { liveText: event.data.text };
        case "reaction/state":
          return {
            reactions: {
              likes: event.data.likes,
              dislikes: event.data.dislikes,
            },
          };
        case "lobby/theme_added":
          return {
            corpusThemes: event.data.corpus_themes,
            ...(event.data.theme_gen_used !== undefined
              ? { themeGenUsed: event.data.theme_gen_used }
              : {}),
          };
        case "lobby/theme_regenerated":
          return {
            corpusThemes: event.data.corpus_themes,
          };
        case "round/concede_state":
          return current.currentRound
            ? {
                currentRound: {
                  ...current.currentRound,
                  conceded_player_ids: event.data.conceded_player_ids,
                },
              }
            : {};
        case "round/letter_reveal":
          return current.currentRound
            ? {
                currentRound: {
                  ...current.currentRound,
                  letter_pattern: event.data.pattern,
                  revealed_indices: event.data.revealed_indices,
                },
              }
            : {};
        case "guess/feed": {
          const message: ChatMessage = {
            id: `${event.data.at}-${event.data.player_id}`,
            player_id: event.data.player_id,
            team_id: event.data.team_id,
            text: event.data.text,
            correct: event.data.correct,
            at: event.data.at,
          };
          const next = [...current.chatFeed, message].slice(-MAX_CHAT_HISTORY);
          return { chatFeed: next };
        }
        case "guess/correct":
          return {
            correctPlayerIds: current.correctPlayerIds.includes(event.data.player_id)
              ? current.correctPlayerIds
              : [...current.correctPlayerIds, event.data.player_id],
            // Update the team's score in the local copy.
            teams: current.teams.map((t) =>
              t.id === event.data.team_id
                ? { ...t, score: event.data.total_team_score }
                : t
            ),
            guessFlash:
              event.data.player_id === current.yourPlayerId
                ? { kind: "correct" }
                : current.guessFlash,
          };
        case "guess/wrong":
          return {
            yourFreeAttemptsLeft: event.data.free_attempts_left,
            yourPaidAttemptsTotal: event.data.paid_attempts_total,
            guessFlash: {
              kind: "wrong",
              free_attempts_left: event.data.free_attempts_left,
              paid_attempts_total: event.data.paid_attempts_total,
            },
          };
        case "guess/penalty":
          return {
            guessFlash: {
              kind: "penalty",
              amount: event.data.amount,
            },
          };
        case "round/ended":
          return {
            currentRound: null,
            describerWord: null,
            liveText: "",
            lastRoundResults: event.data,
            // Update team scores from results.per_team if present.
            teams: current.teams.map((t) => {
              const row = event.data.results?.per_team?.find(
                (r) => r.team_id === t.id
              );
              return row ? { ...t, score: row.new_score } : t;
            }),
          };
        case "board/state":
          return {
            state: "board",
            board: event.data.board,
            currentDescriberId: event.data.current_describer_id,
            currentRound: null,
            ...clearRoundEphemerals(),
          };
        case "game/ended":
          return {
            state: "ended",
            currentRound: null,
            describerWord: null,
            finalScores: event.data.final_scores,
            ...clearRoundEphemerals(),
          };
        case "error":
          return { lastError: { code: event.data.code, ref: event.data.ref } };
        default:
          return {};
      }
    }),

  reset: () => set({ ...empty }),
  clearError: () => set({ lastError: null }),
  clearGuessFlash: () => set({ guessFlash: null }),
  acknowledgeRoundResult: () => set({ lastRoundResults: null }),
}));
