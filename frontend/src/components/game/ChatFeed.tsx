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
      <div className="flex items-baseline justify-between mb-3">
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
          className="max-h-80 overflow-y-auto pr-1 space-y-2.5 text-sm"
        >
          {messages.map((m, i) => {
            const player = players.find((p) => p.id === m.player_id);
            const team = teams.find((t) => t.id === m.team_id);
            const isYou = m.player_id === yourPlayerId;
            const teamColor = team?.color ?? "var(--ink-faint)";
            const nickname = player?.nickname ?? "—";
            const initial = (nickname[0] ?? "?").toUpperCase();

            // Collapse the avatar + name on consecutive messages from the
            // same author, but always show them on a correct-guess row so
            // the celebration reads cleanly.
            const prev = messages[i - 1];
            const compact =
              !!prev && prev.player_id === m.player_id && !m.correct && !prev.correct;

            return (
              <li
                key={m.id}
                className={
                  "flex gap-2 " +
                  (isYou ? "flex-row-reverse" : "flex-row") +
                  (compact ? " -mt-1.5" : "")
                }
              >
                {/* Avatar — hidden on compact follow-ups, kept as a spacer
                    so the bubble alignment stays consistent. */}
                <div
                  aria-hidden
                  className={
                    "shrink-0 grid place-items-center w-7 h-7 rounded-full font-bold text-[0.7rem] uppercase " +
                    (compact ? "opacity-0" : "")
                  }
                  style={{
                    background: teamColor,
                    color: "#fff",
                    border: "2px solid var(--ink)",
                  }}
                >
                  {initial}
                </div>

                <div
                  className={
                    "flex flex-col min-w-0 max-w-[80%] " +
                    (isYou ? "items-end" : "items-start")
                  }
                >
                  {!compact && (
                    <div
                      className={
                        "mb-0.5 px-0.5 text-xs " +
                        (isYou ? "text-right" : "text-left")
                      }
                    >
                      <span
                        className={
                          "font-semibold " +
                          (isYou ? "underline decoration-coral" : "")
                        }
                        style={{ color: teamColor }}
                      >
                        {nickname}
                      </span>
                    </div>
                  )}

                  <div
                    className={
                      "chat-bubble " +
                      (m.correct
                        ? "chat-bubble-correct"
                        : isYou
                          ? "chat-bubble-you"
                          : "chat-bubble-other")
                    }
                  >
                    {m.correct ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span aria-hidden>🎉</span>
                        <span>{t("play.chat_guessed_correctly")}</span>
                        <span
                          aria-label={t("play.chat_correct_aria")}
                          className="font-bold"
                        >
                          ✓
                        </span>
                      </span>
                    ) : (
                      <span className="break-words">{m.text}</span>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
