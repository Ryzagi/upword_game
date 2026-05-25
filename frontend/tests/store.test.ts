import { beforeEach, describe, expect, it } from "vitest";

import type { GameSettings, PlayerPublic, TeamPublic } from "../src/api/rooms";
import { useRoomStore } from "../src/stores/useRoomStore";

const DEFAULT_SETTINGS: GameSettings = {
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

describe("useRoomStore", () => {
  beforeEach(() => {
    useRoomStore.getState().reset();
  });

  it("hydrates from a room/snapshot", () => {
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "lobby",
        host_id: "p1",
        your_player_id: "p1",
        players: [
          player("p1", "Alex", { is_host: true }),
          player("p2", "Mira", { is_connected: false }),
        ],
        teams: [],
        settings: DEFAULT_SETTINGS,
      },
    });
    const s = useRoomStore.getState();
    expect(s.code).toBe("ABCDEF");
    expect(s.yourPlayerId).toBe("p1");
    expect(s.hostId).toBe("p1");
    expect(s.players.map((p) => p.nickname)).toEqual(["Alex", "Mira"]);
    expect(s.settings.mode).toBe("attempts");
  });

  it("updates roster + teams on lobby/state without touching identity fields", () => {
    const team: TeamPublic = {
      id: "t1",
      name: "Red",
      color: "#ef4444",
      score: 0,
      player_ids: ["p2"],
    };
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "lobby",
        host_id: "p1",
        your_player_id: "p1",
        players: [player("p1", "Alex", { is_host: true })],
        teams: [],
        settings: DEFAULT_SETTINGS,
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "lobby/state",
      data: {
        host_id: "p2",
        players: [
          player("p1", "Alex"),
          player("p2", "Mira", { is_host: true, team_id: "t1" }),
        ],
        teams: [team],
        settings: { ...DEFAULT_SETTINGS, team_mode: "teams" },
      },
    });
    const s = useRoomStore.getState();
    expect(s.hostId).toBe("p2");
    expect(s.yourPlayerId).toBe("p1");
    expect(s.teams).toHaveLength(1);
    expect(s.settings.team_mode).toBe("teams");
  });

  it("removes players on lobby/player_left", () => {
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "lobby",
        host_id: "p1",
        your_player_id: "p1",
        players: [player("p1", "Alex", { is_host: true }), player("p2", "Mira")],
        teams: [],
        settings: DEFAULT_SETTINGS,
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "lobby/player_left",
      data: { player_id: "p2" },
    });
    expect(useRoomStore.getState().players.map((p) => p.id)).toEqual(["p1"]);
  });

  it("captures the latest error and lets the consumer clear it", () => {
    useRoomStore.getState().applyServerEvent({
      type: "error",
      data: { code: "nickname_taken", ref: "lobby/rename" },
    });
    expect(useRoomStore.getState().lastError?.code).toBe("nickname_taken");
    useRoomStore.getState().clearError();
    expect(useRoomStore.getState().lastError).toBeNull();
  });

  it("ignores duplicate lobby/player_joined for an existing player", () => {
    useRoomStore.getState().applyServerEvent({
      type: "room/snapshot",
      data: {
        code: "ABCDEF",
        state: "lobby",
        host_id: "p1",
        your_player_id: "p1",
        players: [player("p1", "Alex", { is_host: true })],
        teams: [],
        settings: DEFAULT_SETTINGS,
      },
    });
    useRoomStore.getState().applyServerEvent({
      type: "lobby/player_joined",
      data: { player: player("p1", "Alex", { is_host: true }) },
    });
    expect(useRoomStore.getState().players).toHaveLength(1);
  });
});
