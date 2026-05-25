import { useTranslation } from "react-i18next";

import type {
  BoardPublic,
  PerTeamResult,
  PlayerPublic,
  RoundEndedPayload,
  TeamPublic,
} from "../../api/rooms";
import { Modal } from "../common/Modal";

interface Props {
  open: boolean;
  result: RoundEndedPayload | null;
  board: BoardPublic | null;
  players: PlayerPublic[];
  teams: TeamPublic[];
  onClose: () => void;
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

export function RoundSummaryModal({
  open,
  result,
  board,
  players,
  teams,
  onClose,
}: Props) {
  const { t } = useTranslation();
  if (result === null) return null;

  const theme = board?.themes.find((th) => th.id === result.theme_id);
  const themeName = theme?.name ?? result.theme_id;
  const describer = players.find((p) => p.id === result.describer_id);
  const reason = result.conceded
    ? t("play.reason_conceded")
    : result.forced
      ? t("play.reason_forced")
      : t("play.reason_ended");

  // Sort scoring teams by position (winners first), then by team order.
  const perTeam: PerTeamResult[] = result.results?.per_team ?? [];
  const sorted = [...perTeam].sort((a, b) => {
    const ap = a.position ?? Number.MAX_SAFE_INTEGER;
    const bp = b.position ?? Number.MAX_SAFE_INTEGER;
    return ap - bp;
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      eyebrow={reason}
      title={t("play.summary_title")}
      accent="lilac"
      widthClass="max-w-xl"
    >
      <div className="space-y-4">
        <div className="bento bento-sm bento-yellow p-4">
          <p className="eyebrow">{t("play.the_word_was")}</p>
          <h3 className="headline text-4xl md:text-5xl mt-1 break-words">
            {result.word_text}
          </h3>
          <p className="mt-2 text-sm opacity-80">
            <span className="eyebrow mr-2 align-middle">{t("play.hint")}</span>
            {result.hint}
          </p>
        </div>

        <div className="bento bento-sm p-4">
          <p className="eyebrow mb-1">{t("play.summary_meta")}</p>
          <p className="font-semibold">
            {themeName} ·{" "}
            <span className="numeral">{result.base_score}</span> ·{" "}
            {t("play.summary_describer", {
              describer: describer?.nickname ?? result.describer_id,
            })}
          </p>
        </div>

        {sorted.length > 0 && (
          <div className="space-y-2">
            <p className="eyebrow">{t("play.summary_per_team")}</p>
            <ul className="space-y-2">
              {sorted.map((row) => {
                const team = teams.find((tt) => tt.id === row.team_id);
                if (!team) return null;
                const player = players.find((p) => p.id === row.first_player_id);
                const isWinner = row.position !== null;
                return (
                  <li
                    key={row.team_id}
                    className="bento bento-sm p-3 flex items-center justify-between gap-3"
                    style={{
                      background: team.color,
                      color: contrastInk(team.color),
                    }}
                  >
                    <div className="flex items-baseline gap-3 min-w-0">
                      <span className="numeral text-lg w-6 text-right">
                        {row.position ?? "—"}
                      </span>
                      <div className="min-w-0">
                        <p className="headline text-lg truncate">{team.name}</p>
                        {player && (
                          <p className="text-xs opacity-80">
                            {t("play.summary_first_player", {
                              player: player.nickname,
                            })}
                          </p>
                        )}
                      </div>
                    </div>
                    <span
                      className={
                        "numeral text-2xl " + (isWinner ? "" : "opacity-50")
                      }
                    >
                      {row.points > 0 ? `+${row.points}` : "0"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {result.results && (
          <div className="bento bento-sm bento-mint p-3 flex items-baseline justify-between">
            <div>
              <p className="eyebrow">{t("play.summary_describer_reward")}</p>
              <p className="text-sm mt-1">
                {t("play.summary_describer", {
                  describer: describer?.nickname ?? result.describer_id,
                })}
              </p>
            </div>
            <span className="numeral text-2xl">
              {result.results.describer_points > 0
                ? `+${result.results.describer_points}`
                : "0"}
            </span>
          </div>
        )}

        <button type="button" onClick={onClose} className="btn btn-coral w-full">
          {t("play.summary_continue")}
        </button>
      </div>
    </Modal>
  );
}
