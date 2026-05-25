import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { GameSettings, PlayerPublic, TeamPublic } from "../../api/rooms";
import type { ClientEvent } from "../../ws/events";

interface Props {
  isHost: boolean;
  yourPlayerId: string | null;
  players: PlayerPublic[];
  teams: TeamPublic[];
  settings: GameSettings;
  send: (event: ClientEvent) => boolean;
}

export function TeamPanel({
  isHost,
  yourPlayerId,
  players,
  teams,
  settings,
  send,
}: Props) {
  const { t } = useTranslation();
  const [newTeamName, setNewTeamName] = useState("");
  const [teamCount, setTeamCount] = useState(2);

  const unassigned = players.filter((p) => p.team_id === null);
  const isSolo = settings.team_mode === "solo";

  return (
    <section className="bento p-5 md:p-6 h-full">
      <div className="flex items-baseline justify-between flex-wrap gap-3 mb-4">
        <h2 className="headline text-2xl flex items-center gap-2.5">
          <span className="marker marker-pink" aria-hidden />
          {t("lobby.teams.title")}
        </h2>
        {isHost ? (
          <div className="seg" style={{ background: "var(--bg)" }}>
            <button
              type="button"
              className="seg-btn"
              data-active={isSolo}
              onClick={() =>
                send({ type: "lobby/settings_set", data: { team_mode: "solo" } })
              }
            >
              {t("lobby.teams.mode_solo")}
            </button>
            <button
              type="button"
              className="seg-btn"
              data-active={!isSolo}
              onClick={() =>
                send({
                  type: "lobby/settings_set",
                  data: { team_mode: "teams" },
                })
              }
            >
              {t("lobby.teams.mode_teams")}
            </button>
          </div>
        ) : (
          <span className="chip">
            {isSolo ? t("lobby.teams.mode_solo") : t("lobby.teams.mode_teams")}
          </span>
        )}
      </div>

      {isSolo ? (
        <div className="bento bento-flat bg-white/60 dark:bg-card p-4">
          <p className="font-medium">{t("lobby.teams.solo_hint")}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {teams.length === 0 && (
            <p className="font-medium opacity-80">{t("lobby.teams.empty")}</p>
          )}
          <ul className="grid sm:grid-cols-2 gap-3">
            {teams.map((team) => (
              <TeamCard
                key={team.id}
                team={team}
                players={players}
                isHost={isHost}
                yourPlayerId={yourPlayerId}
                send={send}
              />
            ))}
          </ul>

          {unassigned.length > 0 && (
            <div
              className="bento bento-sm p-3"
              style={{ background: "var(--bg)" }}
            >
              <p className="eyebrow mb-1">{t("lobby.teams.unassigned")}</p>
              <ul className="flex flex-wrap gap-1.5">
                {unassigned.map((p) => (
                  <li key={p.id} className="chip" style={{ background: "var(--card)" }}>
                    {p.nickname}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {isHost && (
            <div
              className="bento bento-sm p-4 space-y-3"
              style={{ background: "var(--bg)" }}
            >
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const name = newTeamName.trim();
                  if (!name) return;
                  send({ type: "lobby/team_create", data: { name } });
                  setNewTeamName("");
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  placeholder={t("lobby.teams.new_team_placeholder")}
                  maxLength={24}
                  className="field"
                />
                <button
                  type="submit"
                  disabled={!newTeamName.trim()}
                  className="btn btn-sm btn-yellow whitespace-nowrap"
                >
                  + {t("lobby.teams.add_team")}
                </button>
              </form>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="eyebrow">
                  {t("lobby.teams.randomize_label")}
                </span>
                <input
                  type="number"
                  min={1}
                  max={8}
                  value={teamCount}
                  onChange={(e) =>
                    setTeamCount(
                      Math.max(1, Math.min(8, Number(e.target.value) || 2))
                    )
                  }
                  className="field !w-16 text-center font-bold"
                />
                <button
                  type="button"
                  onClick={() =>
                    send({
                      type: "lobby/randomize_teams",
                      data: { team_count: teamCount },
                    })
                  }
                  className="btn btn-sm btn-coral"
                >
                  🎲 {t("lobby.teams.randomize")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function TeamCard({
  team,
  players,
  isHost,
  yourPlayerId,
  send,
}: {
  team: TeamPublic;
  players: PlayerPublic[];
  isHost: boolean;
  yourPlayerId: string | null;
  send: (event: ClientEvent) => boolean;
}) {
  const { t } = useTranslation();
  const [renameDraft, setRenameDraft] = useState<string | null>(null);
  const members = players.filter((p) => team.player_ids.includes(p.id));
  const meInTeam =
    yourPlayerId !== null && team.player_ids.includes(yourPlayerId);

  return (
    <li
      className="bento bento-sm p-3 flex flex-col gap-2"
      style={{ background: team.color, color: contrastInk(team.color) }}
    >
      <div className="flex items-center justify-between gap-2">
        {renameDraft === null ? (
          <h3 className="headline text-lg truncate flex items-baseline gap-2">
            {team.name}
            <span className="numeral text-xs opacity-70">({members.length})</span>
          </h3>
        ) : (
          <input
            type="text"
            value={renameDraft}
            onChange={(e) => setRenameDraft(e.target.value)}
            maxLength={24}
            autoFocus
            onBlur={() => {
              const trimmed = renameDraft.trim();
              if (trimmed && trimmed !== team.name) {
                send({
                  type: "lobby/team_rename",
                  data: { team_id: team.id, name: trimmed },
                });
              }
              setRenameDraft(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") setRenameDraft(null);
            }}
            className="field !p-1.5 text-base font-bold"
          />
        )}
        <div className="flex gap-1">
          {!meInTeam ? (
            <button
              type="button"
              onClick={() =>
                send({
                  type: "lobby/team_set",
                  data: { player_id: yourPlayerId ?? "", team_id: team.id },
                })
              }
              disabled={yourPlayerId === null}
              className="btn btn-sm btn-ghost"
            >
              {t("lobby.teams.join")}
            </button>
          ) : (
            <button
              type="button"
              onClick={() =>
                send({
                  type: "lobby/team_set",
                  data: { player_id: yourPlayerId ?? "", team_id: null },
                })
              }
              className="btn btn-sm btn-ghost"
            >
              {t("lobby.teams.leave")}
            </button>
          )}
          {isHost && (
            <button
              type="button"
              onClick={() => setRenameDraft(team.name)}
              className="btn btn-sm btn-ghost"
              aria-label={t("lobby.teams.rename")}
            >
              ✎
            </button>
          )}
          {isHost && (
            <button
              type="button"
              onClick={() => {
                const ok = window.confirm(
                  t("lobby.teams.delete_confirm", { name: team.name })
                );
                if (!ok) return;
                send({
                  type: "lobby/team_delete",
                  data: { team_id: team.id },
                });
              }}
              className="btn btn-sm btn-coral"
              aria-label={t("lobby.teams.delete")}
            >
              ✕
            </button>
          )}
        </div>
      </div>
      {members.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5">
          {members.map((p) => (
            <li
              key={p.id}
              className="chip"
              style={{ background: "var(--bg)", color: "var(--ink)" }}
            >
              {p.nickname}
              {isHost && p.id !== yourPlayerId && (
                <button
                  type="button"
                  onClick={() =>
                    send({
                      type: "lobby/team_set",
                      data: { player_id: p.id, team_id: null },
                    })
                  }
                  aria-label={t("lobby.teams.unassign", { name: p.nickname })}
                  className="ml-1 opacity-70 hover:opacity-100"
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm opacity-70 italic">{t("lobby.teams.empty_card")}</p>
      )}
    </li>
  );
}

/** Pick black or white text for a given background hex for contrast. */
function contrastInk(hex: string): string {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return "#13110a";
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  // Perceived luminance (Rec. 709, rough).
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return lum > 0.62 ? "#13110a" : "#ffffff";
}
