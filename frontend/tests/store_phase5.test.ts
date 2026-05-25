import { beforeEach, describe, expect, it } from "vitest";

import type {
  BoardPublic,
  GameSettings,
  PlayerPublic,
  RoundPublic,
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
  themes: [{ id: "sport", name: "Sport" }],
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

describe("useRoomStore — phase 5 reactions", () => {
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
        settings: SETTINGS,
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

  it("reaction/state replaces likes and dislikes", () => {
    useRoomStore.getState().applyServerEvent({
      type: "reaction/state",
      data: { likes: ["p2"], dislikes: [] },
    });
    expect(useRoomStore.getState().reactions).toEqual({
      likes: ["p2"],
      dislikes: [],
    });
    useRoomStore.getState().applyServerEvent({
      type: "reaction/state",
      data: { likes: [], dislikes: ["p2"] },
    });
    expect(useRoomStore.getState().reactions).toEqual({
      likes: [],
      dislikes: ["p2"],
    });
  });

  it("reactions reset when a new round starts", () => {
    useRoomStore.getState().applyServerEvent({
      type: "reaction/state",
      data: { likes: ["p2"], dislikes: [] },
    });
    useRoomStore.getState().applyServerEvent({
      type: "round/started",
      data: { ...ROUND, id: "r-2", difficulty: 2, base_score: 200 },
    });
    expect(useRoomStore.getState().reactions).toEqual({ likes: [], dislikes: [] });
  });

  it("reactions clear on board/state (between rounds)", () => {
    useRoomStore.getState().applyServerEvent({
      type: "reaction/state",
      data: { likes: ["p2"], dislikes: [] },
    });
    useRoomStore.getState().applyServerEvent({
      type: "board/state",
      data: {
        board: BOARD,
        scoreboard: [],
        current_describer_id: "p2",
      },
    });
    expect(useRoomStore.getState().reactions).toEqual({ likes: [], dislikes: [] });
  });

  it("snapshot rehydrates reactions from current_round.reactions", () => {
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
        settings: SETTINGS,
        board: BOARD,
        current_round: {
          ...ROUND,
          reactions: { likes: ["p2"], dislikes: [] },
        },
        current_describer_id: "p1",
        describer_queue: ["p1", "p2"],
      },
    });
    expect(useRoomStore.getState().reactions).toEqual({
      likes: ["p2"],
      dislikes: [],
    });
  });
});
