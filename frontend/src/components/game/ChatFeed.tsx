import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import type { PlayerPublic, TeamPublic } from "../../api/rooms";
import type { ChatMessage } from "../../stores/useRoomStore";

interface Props {
  messages: ChatMessage[];
  players: PlayerPublic[];
  teams: TeamPublic[];
  yourPlayerId: string | null;
}

export function ChatFeed({ messages, players, teams, yourPlayerId }: Props) {
  const { t } = useTranslation();
  const listRef = useRef<HTMLOListElement | null>(null);

  // Keep the most recent guess in view as new messages stream in.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  return (
    <section className="bento p-4 md:p-5">
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="headline text-lg flex items-center gap-2">
          <span className="marker marker-mint" aria-hidden />
          {t("play.chat_title")}
        </h2>
        <span className="eyebrow">
          {t("play.chat_count", { count: messages.length })}
        </span>
      </div>
      {messages.length === 0 ? (
        <p className="text-sm text-ink-soft italic">{t("play.chat_empty")}</p>
      ) : (
        <ol
          ref={listRef}
          role="log"
          aria-live="polite"
          aria-relevant="additions"
          className="max-h-72 overflow-y-auto pr-1 space-y-1.5 text-sm"
        >
          {messages.map((m) => {
            const player = players.find((p) => p.id === m.player_id);
            const team = teams.find((t) => t.id === m.team_id);
            const isYou = m.player_id === yourPlayerId;
            return (
              <li
                key={m.id}
                className={
                  "flex items-baseline gap-2 leading-snug " +
                  (m.correct
                    ? "bg-mint/40 rounded px-1.5 py-0.5"
                    : "")
                }
              >
                <span
                  className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                  aria-hidden
                  style={{
                    background: team?.color ?? "var(--ink-faint)",
                    transform: "translateY(-1px)",
                  }}
                />
                <span
                  className={
                    "font-semibold shrink-0 " +
                    (isYou ? "underline decoration-coral" : "")
                  }
                  style={{ color: team?.color ?? "var(--ink)" }}
                >
                  {player?.nickname ?? "—"}
                </span>
                <span className="text-ink break-words flex-1 min-w-0">
                  {m.text}
                </span>
                {m.correct && (
                  <span
                    aria-label={t("play.chat_correct_aria")}
                    className="text-emerald-600 font-bold"
                  >
                    ✓
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
