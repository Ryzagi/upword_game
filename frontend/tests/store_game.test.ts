import { beforeEach, describe, expect, it } from "vitest";

import type {
  BoardPublic,
  GameSettings,
  PlayerPublic,
  RoundPublic,
  ScoreboardEntry,
} from "../src/api/rooms";
import { useRoomStore } from "../src/stores/useRoomStore";

const SETTINGS: GameSettings = {
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
  themes: [
    { id: "sport", name: "Sport", icon: "trophy" },
    { id: "nature", name: "Nature", icon: "leaf" },
  ],
  base_values: [100, 200, 300, 400, 500],
  used: [],
};

const SCOREBOARD: ScoreboardEntry[] = [
  { team_id: "t1", name: "Alex", color: "#ef4444", score: 0 },
  { team_id: "t2", name: "Mira", color: "#3b82f6", score: 0 },
];

const ROUND: RoundPublic = {
  id: "r-1",
  describer_id: "p1",
  theme_id: "sport",
  difficulty: 3,
  base_score: 300,
  started_at: "2026-05-25T08:00:00Z",
  ends_at: null,
  state: "active",
};

function player(
  id: string,
  nickname: string,
  extras: Partial<PlayerPublic> = {}
): PlayerPublic {
  return {
    id,
    nickname,
    is_host: false,
    is_connected: true,
    team_id: null,
    ...extras,
  };
}

describe("useRoomStore — game flow reducers", () => {
  beforeEach(() => {
    useRoomStore.getState().reset();
    // Hydrate a base lobby state so identity fields are present.
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "lobby",
        host_id: "p1",
        your_player_id: "p1",
        players: [
          player("p1", "Alex", { is_host: true, team_id: "t1" }),
          player("p2", "Mira", { team_id: "t2" }),
        ],
        teams: [
          { id: "t1", name: "Alex", color: "#ef4444", score: 0, player_ids: ["p1"] },
          { id: "t2", name: "Mira", color: "#3b82f6", score: 0, player_ids: ["p2"] },
        ],
        settings: SETTINGS,
      },
    });
  });

  it("game/started populates board + describerQueue + current describer + flips state", () => {
    useRoomStore.getState().applyServerEvent({
      type: "game/started",
      data: {
        board: BOARD,
        scoreboard: SCOREBOARD,
        describer_queue: ["p1", "p2"],
        current_describer_id: "p1",
      },
    });
    const s = useRoomStore.getState();
    expect(s.state).toBe("board");
    expect(s.board).toEqual(BOARD);
    expect(s.describerQueue).toEqual(["p1", "p2"]);
    expect(s.currentDescriberId).toBe("p1");
    expect(s.currentRound).toBeNull();
    expect(s.describerWord).toBeNull();
  });

  it("round/started sets currentRound + describer, transitions to round", () => {
    useRoomStore.getState().applyServerEvent({
      type: "game/started",
      data: {
        board: BOARD,
        scoreboard: SCOREBOARD,
        describer_queue: ["p1", "p2"],
        current_describer_id: "p1",
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "round/started",
      data: ROUND,
    });
    const s = useRoomStore.getState();
    expect(s.state).toBe("round");
    expect(s.currentRound).toEqual(ROUND);
    expect(s.currentDescriberId).toBe("p1");
  });

  it("describer/word lands in describerWord without disturbing currentRound", () => {
    useRoomStore.getState().applyServerEvent({
      type: "game/started",
      data: {
        board: BOARD,
        scoreboard: SCOREBOARD,
        describer_queue: ["p1"],
        current_describer_id: "p1",
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "round/started",
      data: ROUND,
    });
    useRoomStore.getState().applyServerEvent({
      type: "describer/word",
      data: { word_id: "w-1", word_text: "kettle", hint: "boils water" },
    });
    const s = useRoomStore.getState();
    expect(s.describerWord).toEqual({
      word_id: "w-1",
      word_text: "kettle",
      hint: "boils water",
    });
    expect(s.currentRound).toEqual(ROUND);
  });

  it("round/ended clears currentRound + describerWord, stashes lastRoundResults", () => {
    useRoomStore.getState().applyServerEvent({
      type: "game/started",
      data: {
        board: BOARD,
        scoreboard: SCOREBOARD,
        describer_queue: ["p1"],
        current_describer_id: "p1",
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "round/started",
      data: ROUND,
    });
    useRoomStore.getState().applyServerEvent({
      type: "describer/word",
      data: { word_id: "w-1", word_text: "kettle", hint: "boils water" },
    });
    useRoomStore.getState().applyServerEvent({
      type: "round/ended",
      data: {
        round_id: "r-1",
        describer_id: "p1",
        theme_id: "sport",
        difficulty: 3,
        base_score: 300,
        word_text: "kettle",
        hint: "boils water",
        conceded: true,
        forced: false,
        results: {
          describer_id: "p1",
          describer_team_id: "t1",
          describer_points: 0,
          correct_non_describer_team_count: 0,
          scored_team_ids: [],
          per_team: [],
          per_player_attempts: [],
        },
      },
    });
    const s = useRoomStore.getState();
    expect(s.currentRound).toBeNull();
    expect(s.describerWord).toBeNull();
    expect(s.lastRoundResults?.word_text).toBe("kettle");
    expect(s.lastRoundResults?.conceded).toBe(true);
  });

  it("acknowledgeRoundResult clears lastRoundResults", () => {
    useRoomStore.getState().applyServerEvent({
      type: "round/ended",
      data: {
        round_id: "r-1",
        describer_id: "p1",
        theme_id: "sport",
        difficulty: 3,
        base_score: 300,
        word_text: "kettle",
        hint: "boils water",
        conceded: true,
        forced: false,
        results: {
          describer_id: "p1",
          describer_team_id: "t1",
          describer_points: 0,
          correct_non_describer_team_count: 0,
          scored_team_ids: [],
          per_team: [],
          per_player_attempts: [],
        },
      },
    });
    expect(useRoomStore.getState().lastRoundResults).not.toBeNull();
    useRoomStore.getState().acknowledgeRoundResult();
    expect(useRoomStore.getState().lastRoundResults).toBeNull();
  });

  it("board/state updates board and rotates the describer", () => {
    useRoomStore.getState().applyServerEvent({
      type: "board/state",
      data: {
        board: { ...BOARD, used: [{ theme_id: "sport", difficulty: 3 }] },
        scoreboard: SCOREBOARD,
        current_describer_id: "p2",
      },
    });
    const s = useRoomStore.getState();
    expect(s.state).toBe("board");
    expect(s.board?.used).toEqual([{ theme_id: "sport", difficulty: 3 }]);
    expect(s.currentDescriberId).toBe("p2");
    expect(s.currentRound).toBeNull();
  });

  it("game/ended sets finalScores + state=ended", () => {
    useRoomStore.getState().applyServerEvent({
      type: "game/ended",
      data: {
        final_scores: [
          { team_id: "t1", name: "Alex", color: "#ef4444", score: 480 },
          { team_id: "t2", name: "Mira", color: "#3b82f6", score: 220 },
        ],
      },
    });
    const s = useRoomStore.getState();
    expect(s.state).toBe("ended");
    expect(s.finalScores?.[0].name).toBe("Alex");
    expect(s.finalScores?.[0].score).toBe(480);
  });

  it("snapshot mid-round populates board + currentRound + describerWord", () => {
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "round",
        host_id: "p1",
        your_player_id: "p1",
        players: [
          player("p1", "Alex", { is_host: true, team_id: "t1" }),
          player("p2", "Mira", { team_id: "t2" }),
        ],
        teams: [
          { id: "t1", name: "Alex", color: "#ef4444", score: 0, player_ids: ["p1"] },
          { id: "t2", name: "Mira", color: "#3b82f6", score: 0, player_ids: ["p2"] },
        ],
        settings: SETTINGS,
        board: BOARD,
        current_round: ROUND,
        current_describer_id: "p1",
        describer_queue: ["p1", "p2"],
        your_describer_word: { word_id: "w-1", word_text: "kettle", hint: "boils water" },
      },
    });
    const s = useRoomStore.getState();
    expect(s.state).toBe("round");
    expect(s.board?.themes).toHaveLength(2);
    expect(s.currentRound?.theme_id).toBe("sport");
    expect(s.describerWord?.word_text).toBe("kettle");
  });
});
