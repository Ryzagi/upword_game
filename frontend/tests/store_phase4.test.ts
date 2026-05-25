import { beforeEach, describe, expect, it } from "vitest";

import type {
  BoardPublic,
  GameSettings,
  PlayerPublic,
  RoundPublic,
} from "../src/api/rooms";
import { useRoomStore } from "../src/stores/useRoomStore";

const SETTINGS_ATTEMPTS: GameSettings = {
  team_mode: "solo",
  mode: "attempts",
  time_seconds: 60,
  attempts_per_round: 5,
  scoring: {
    base_values: [100, 200, 300, 400, 500],
    decay: 0.8,
    penalty_per_attempt: 10,
    describer_base_pct: 0.5,
    describer_bonus_pct: 0.1,
  },
};

const BOARD: BoardPublic = {
  themes: [{ id: "sport", name: "Sport", icon: "trophy" }],
  base_values: [100, 200, 300, 400, 500],
  used: [],
};

const ROUND: RoundPublic = {
  id: "r-1",
  describer_id: "p1",
  theme_id: "sport",
  difficulty: 1,
  base_score: 100,
  started_at: "2026-05-25T08:00:00Z",
  ends_at: null,
  state: "active",
  live_text: "",
};

function player(id: string, nick: string, extras: Partial<PlayerPublic> = {}): PlayerPublic {
  return {
    id,
    nickname: nick,
    is_host: false,
    is_connected: true,
    team_id: null,
    ...extras,
  };
}

describe("useRoomStore — phase 4 reducers", () => {
  beforeEach(() => {
    useRoomStore.getState().reset();
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "lobby",
        host_id: "p1",
        your_player_id: "p2",
        players: [
          player("p1", "Alex", { is_host: true, team_id: "t1" }),
          player("p2", "Mira", { team_id: "t2" }),
        ],
        teams: [
          { id: "t1", name: "Alex", color: "#ef4444", score: 0, player_ids: ["p1"] },
          { id: "t2", name: "Mira", color: "#3b82f6", score: 0, player_ids: ["p2"] },
        ],
        settings: SETTINGS_ATTEMPTS,
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "game/started",
      data: {
        board: BOARD,
        scoreboard: [],
        describer_queue: ["p1", "p2"],
        current_describer_id: "p1",
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "round/started",
      data: ROUND,
    });
  });

  it("describer/text replaces liveText", () => {
    useRoomStore.getState().applyServerEvent({
      type: "describer/text",
      data: { text: "round object…" },
    });
    expect(useRoomStore.getState().liveText).toBe("round object…");
  });

  it("guess/wrong decrements free attempts and sets a wrong flash", () => {
    useRoomStore.getState().applyServerEvent({
      type: "guess/wrong",
      data: { free_attempts_left: 4, paid_attempts_total: 0 },
    });
    const s = useRoomStore.getState();
    expect(s.yourFreeAttemptsLeft).toBe(4);
    expect(s.yourPaidAttemptsTotal).toBe(0);
    expect(s.guessFlash?.kind).toBe("wrong");
  });

  it("guess/penalty sets a penalty flash", () => {
    useRoomStore.getState().applyServerEvent({
      type: "guess/penalty",
      data: { amount: 10, new_balance: -10 },
    });
    expect(useRoomStore.getState().guessFlash?.kind).toBe("penalty");
    expect(useRoomStore.getState().guessFlash?.amount).toBe(10);
  });

  it("guess/correct adds player to correctPlayerIds and bumps team score", () => {
    useRoomStore.getState().applyServerEvent({
      type: "guess/correct",
      data: {
        player_id: "p2",
        team_id: "t2",
        position: 1,
        points_awarded: 100,
        total_team_score: 100,
      },
    });
    const s = useRoomStore.getState();
    expect(s.correctPlayerIds).toContain("p2");
    expect(s.teams.find((t) => t.id === "t2")?.score).toBe(100);
    // Since the guess was from "you" (p2), the flash should be "correct".
    expect(s.guessFlash?.kind).toBe("correct");
  });

  it("round/ended applies team scores from per_team and clears live state", () => {
    useRoomStore.getState().applyServerEvent({
      type: "describer/text",
      data: { text: "round and bouncy" },
    });
    useRoomStore.getState().applyServerEvent({
      type: "round/ended",
      data: {
        round_id: "r-1",
        describer_id: "p1",
        theme_id: "sport",
        difficulty: 1,
        base_score: 100,
        word_text: "ball",
        hint: "a round object",
        conceded: false,
        forced: false,
        results: {
          describer_id: "p1",
          describer_team_id: "t1",
          describer_points: 50,
          correct_non_describer_team_count: 1,
          scored_team_ids: ["t2"],
          per_team: [
            {
              team_id: "t1",
              first_player_id: null,
              correct_at: null,
              position: null,
              points: 0,
              new_score: 50,
            },
            {
              team_id: "t2",
              first_player_id: "p2",
              correct_at: "2026-05-25T08:00:10Z",
              position: 1,
              points: 100,
              new_score: 100,
            },
          ],
          per_player_attempts: [],
        },
      },
    });
    const s = useRoomStore.getState();
    expect(s.currentRound).toBeNull();
    expect(s.describerWord).toBeNull();
    expect(s.liveText).toBe("");
    // Team scores updated from per_team.new_score
    expect(s.teams.find((t) => t.id === "t1")?.score).toBe(50);
    expect(s.teams.find((t) => t.id === "t2")?.score).toBe(100);
    expect(s.lastRoundResults?.results?.describer_points).toBe(50);
  });

  it("snapshot mid-round restores attempts budget and liveText", () => {
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "round",
        host_id: "p1",
        your_player_id: "p2",
        players: [
          player("p1", "Alex", { is_host: true, team_id: "t1" }),
          player("p2", "Mira", { team_id: "t2" }),
        ],
        teams: [
          { id: "t1", name: "Alex", color: "#ef4444", score: 0, player_ids: ["p1"] },
          { id: "t2", name: "Mira", color: "#3b82f6", score: 0, player_ids: ["p2"] },
        ],
        settings: SETTINGS_ATTEMPTS,
        board: BOARD,
        current_round: { ...ROUND, live_text: "in progress" },
        current_describer_id: "p1",
        describer_queue: ["p1", "p2"],
      },
    });
    const s = useRoomStore.getState();
    expect(s.liveText).toBe("in progress");
    // Snapshot reseeds attempts budget from settings.
    expect(s.yourFreeAttemptsLeft).toBe(5);
  });

  it("snapshot with your_round_state restores actual attempt counters", () => {
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "round",
        host_id: "p1",
        your_player_id: "p2",
        players: [
          player("p1", "Alex", { is_host: true, team_id: "t1" }),
          player("p2", "Mira", { team_id: "t2" }),
        ],
        teams: [
          { id: "t1", name: "Alex", color: "#ef4444", score: 0, player_ids: ["p1"] },
          { id: "t2", name: "Mira", color: "#3b82f6", score: 0, player_ids: ["p2"] },
        ],
        settings: SETTINGS_ATTEMPTS,
        board: BOARD,
        current_round: { ...ROUND, live_text: "" },
        current_describer_id: "p1",
        describer_queue: ["p1", "p2"],
        your_round_state: {
          free_attempts_left: 2,
          paid_attempts_total: 1,
          you_have_guessed_correctly: false,
        },
      },
    });
    const s = useRoomStore.getState();
    expect(s.yourFreeAttemptsLeft).toBe(2);
    expect(s.yourPaidAttemptsTotal).toBe(1);
    expect(s.correctPlayerIds).not.toContain("p2");
  });

  it("snapshot with you_have_guessed_correctly seeds correctPlayerIds", () => {
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "round",
        host_id: "p1",
        your_player_id: "p2",
        players: [
          player("p1", "Alex", { is_host: true, team_id: "t1" }),
          player("p2", "Mira", { team_id: "t2" }),
        ],
        teams: [
          { id: "t1", name: "Alex", color: "#ef4444", score: 0, player_ids: ["p1"] },
          { id: "t2", name: "Mira", color: "#3b82f6", score: 0, player_ids: ["p2"] },
        ],
        settings: SETTINGS_ATTEMPTS,
        board: BOARD,
        current_round: ROUND,
        current_describer_id: "p1",
        describer_queue: ["p1", "p2"],
        your_round_state: {
          free_attempts_left: 4,
          paid_attempts_total: 0,
          you_have_guessed_correctly: true,
        },
      },
    });
    expect(useRoomStore.getState().correctPlayerIds).toContain("p2");
  });
});
