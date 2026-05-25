import { useTranslation } from "react-i18next";

import type { PlayerPublic, ScoreboardEntry, TeamPublic } from "../../api/rooms";
import type { ClientEvent } from "../../ws/events";

interface Props {
  finalScores: ScoreboardEntry[] | null;
  teams: TeamPublic[];
  players: PlayerPublic[];
  yourPlayerId: string | null;
  isHost: boolean;
  send: (event: ClientEvent) => boolean;
}

function contrastInk(hex: string): string {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return "#13110a";
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return lum > 0.62 ? "#13110a" : "#ffffff";
}

export function EndedView({
  finalScores,
  teams,
  players,
  yourPlayerId,
  isHost,
  send,
}: Props) {
  const { t } = useTranslation();
  const scores = finalScores ?? teams.map((t) => ({
    team_id: t.id,
    name: t.name,
    color: t.color,
    score: t.score,
  }));
  const ranked = [...scores].sort((a, b) => b.score - a.score);
  const top = ranked[0];

  return (
    <div className="space-y-6">
      <section className="bento bento-coral bento-lg p-8 md:p-12 text-white text-center pop-in" data-order="1">
        <p className="eyebrow text-white/80">{t("ended.kicker")}</p>
        <h2 className="headline-tight text-6xl md:text-8xl mt-3">
          {t("ended.title")}
        </h2>
        {top && (
          <p className="mt-6 text-2xl">
            {t("ended.winner_announcement", { team: top.name })}
          </p>
        )}
      </section>

      <section className="bento p-5 md:p-7 pop-in" data-order="2">
        <h3 className="headline text-2xl mb-4">{t("ended.final_scores")}</h3>
        <ol className="space-y-2">
          {ranked.map((entry, idx) => {
            const team = teams.find((t) => t.id === entry.team_id);
            const members = team
              ? players.filter((p) => team.player_ids.includes(p.id))
              : [];
            return (
              <li
                key={entry.team_id}
                className="bento bento-sm p-3"
                style={{
                  background: entry.color,
                  color: contrastInk(entry.color),
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-baseline gap-3 min-w-0">
                    <span className="numeral text-2xl">{idx + 1}</span>
                    <span className="headline text-xl truncate">
                      {entry.name}
                    </span>
                  </div>
                  <span className="numeral text-3xl">{entry.score}</span>
                </div>
                {members.length > 0 && (
                  <p className="text-xs mt-1 opacity-90">
                    {members
                      .map((m) =>
                        m.id === yourPlayerId ? `${m.nickname} (${t("lobby.you_marker_chip")})` : m.nickname
                      )
                      .join(" · ")}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      {isHost && (
        <section className="bento bento-yellow p-5 md:p-6 pop-in flex items-center justify-between gap-4 flex-wrap" data-order="3">
          <div>
            <p className="eyebrow">{t("ended.play_again_kicker")}</p>
            <h3 className="headline text-2xl mt-1">
              {t("ended.play_again_heading")}
            </h3>
          </div>
          <button
            type="button"
            onClick={() => send({ type: "game/play_again" })}
            className="btn btn-coral text-lg px-6 py-3"
          >
            {t("ended.play_again")} →
          </button>
        </section>
      )}
      {!isHost && (
        <p className="text-center opacity-80">
          {t("ended.waiting_for_host")}
        </p>
      )}
    </div>
  );
}
