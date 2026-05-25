import { useTranslation } from "react-i18next";

import type {
  PlayerId,
  PlayerPublic,
  ReactionState,
  TeamPublic,
} from "../../api/rooms";
import type { ClientEvent } from "../../ws/events";

interface Props {
  teams: TeamPublic[];
  players: PlayerPublic[];
  currentDescriberId: PlayerId | null;
  yourPlayerId: PlayerId | null;
  /** When state==='round' and we want the like/dislike controls visible
   *  next to the describer in the scoreboard. */
  reactions?: ReactionState;
  inRound?: boolean;
  send?: (event: ClientEvent) => boolean;
}

/** Pick black or white text for a given background hex for contrast. */
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

export function Scoreboard({
  teams,
  players,
  currentDescriberId,
  yourPlayerId,
  reactions,
  inRound = false,
  send,
}: Props) {
  const { t } = useTranslation();
  const sorted = [...teams].sort((a, b) => b.score - a.score);
  return (
    <section className="bento p-4 md:p-5">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="headline text-xl">{t("play.scoreboard")}</h2>
      </div>
      <ul className="space-y-2">
        {sorted.map((team) => {
          const members = players.filter((p) => team.player_ids.includes(p.id));
          const teamHasDescriber = members.some(
            (m) => m.id === currentDescriberId
          );
          return (
            <li
              key={team.id}
              className={
                "bento bento-sm p-3 " +
                (teamHasDescriber
                  ? "outline outline-3 outline-offset-2 outline-coral"
                  : "")
              }
              style={{ background: team.color, color: contrastInk(team.color) }}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="headline text-lg truncate">{team.name}</span>
                <span className="numeral text-2xl">{team.score}</span>
              </div>
              <ul className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-xs opacity-90">
                {members.map((m, i) => (
                  <li key={m.id} className="flex items-baseline gap-1.5">
                    {i > 0 && <span className="opacity-60">·</span>}
                    <span
                      className={
                        m.id === yourPlayerId ? "font-semibold underline" : ""
                      }
                    >
                      {m.nickname}
                    </span>
                    {m.id === currentDescriberId && (
                      <span className="text-[0.65rem] uppercase tracking-wide font-bold">
                        ☞ {t("play.describing")}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              {/* Reactions attach to the team that contains the describer. */}
              {inRound && teamHasDescriber && reactions && (
                <DescriberReactions
                  reactions={reactions}
                  yourPlayerId={yourPlayerId}
                  isSelfDescribing={
                    yourPlayerId !== null && yourPlayerId === currentDescriberId
                  }
                  contrastColor={contrastInk(team.color)}
                  send={send}
                />
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function DescriberReactions({
  reactions,
  yourPlayerId,
  isSelfDescribing,
  contrastColor,
  send,
}: {
  reactions: ReactionState;
  yourPlayerId: PlayerId | null;
  isSelfDescribing: boolean;
  contrastColor: string;
  send?: (event: ClientEvent) => boolean;
}) {
  const { t } = useTranslation();
  const youLiked = yourPlayerId !== null && reactions.likes.includes(yourPlayerId);
  const youDisliked =
    yourPlayerId !== null && reactions.dislikes.includes(yourPlayerId);

  // The pill border + text use the contrast color picked for the team bg
  // (black on light teams, white on dark teams) so they read in both cases.
  const isDarkContrast = contrastColor === "#13110a";

  return (
    <div className="mt-2 flex items-center gap-1.5">
      {isSelfDescribing || !send ? (
        <>
          <ReactionPill
            kind="like"
            n={reactions.likes.length}
            isDarkContrast={isDarkContrast}
          />
          <ReactionPill
            kind="dislike"
            n={reactions.dislikes.length}
            isDarkContrast={isDarkContrast}
          />
        </>
      ) : (
        <>
          <ReactionPill
            kind="like"
            n={reactions.likes.length}
            active={youLiked}
            isDarkContrast={isDarkContrast}
            onClick={() =>
              send({ type: "reaction/toggle", data: { kind: "like" } })
            }
            aria-label={t("play.reaction_like_aria")}
          />
          <ReactionPill
            kind="dislike"
            n={reactions.dislikes.length}
            active={youDisliked}
            isDarkContrast={isDarkContrast}
            onClick={() =>
              send({ type: "reaction/toggle", data: { kind: "dislike" } })
            }
            aria-label={t("play.reaction_dislike_aria")}
          />
        </>
      )}
    </div>
  );
}

function ReactionPill({
  kind,
  n,
  active = false,
  isDarkContrast,
  onClick,
  ...rest
}: {
  kind: "like" | "dislike";
  n: number;
  active?: boolean;
  isDarkContrast: boolean;
  onClick?: () => void;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const emoji = kind === "like" ? "👍" : "👎";
  const baseBorder = isDarkContrast ? "border-black/30" : "border-white/40";
  const baseBg = isDarkContrast ? "bg-black/5" : "bg-white/10";
  const activeBg =
    kind === "like" ? "!bg-mint !text-ink" : "!bg-pink !text-ink";
  const cls =
    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold border transition-colors " +
    baseBorder +
    " " +
    baseBg +
    (active ? " " + activeBg : "");
  if (!onClick) {
    return (
      <span className={cls} aria-hidden>
        <span>{emoji}</span>
        <span className="numeral">{n}</span>
      </span>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls} {...rest}>
      <span aria-hidden>{emoji}</span>
      <span className="numeral">{n}</span>
    </button>
  );
}
