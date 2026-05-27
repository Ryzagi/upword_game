import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  BoardPublic,
  DescriberWord,
  GameSettings,
  PlayerPublic,
  RoundPublic,
} from "../../api/rooms";
import { formatSeconds, useCountdown } from "../../lib/countdown";
import { useThrottledCallback } from "../../lib/throttle";
import type { GuessFlash } from "../../stores/useRoomStore";
import type { ClientEvent } from "../../ws/events";
import { TranslateBar } from "./TranslateBar";

interface Props {
  round: RoundPublic;
  board: BoardPublic | null;
  describer: PlayerPublic | null;
  isDescriber: boolean;
  isHost: boolean;
  settings: GameSettings;
  describerWord: DescriberWord | null;
  liveText: string;
  yourFreeAttemptsLeft: number | null;
  yourPaidAttemptsTotal: number;
  guessFlash: GuessFlash | null;
  hasAlreadyGuessedCorrectly: boolean;
  yourPlayerId: string | null;
  roomLanguage: string;
  uiLanguage: string;
  send: (event: ClientEvent) => boolean;
  clearGuessFlash: () => void;
}

const TEXT_THROTTLE_MS = 100;

export function RoundView(props: Props) {
  const {
    round,
    board,
    describer,
    isDescriber,
    isHost,
    settings,
    describerWord,
    liveText,
    yourFreeAttemptsLeft,
    yourPaidAttemptsTotal,
    guessFlash,
    hasAlreadyGuessedCorrectly,
    roomLanguage,
    uiLanguage,
    send,
    clearGuessFlash,
  } = props;
  const { t } = useTranslation();
  const theme = board?.themes.find((th) => th.id === round.theme_id);
  const themeName = theme?.name ?? round.theme_id;
  const secondsLeft = useCountdown(round.ends_at);

  return (
    <section className="space-y-5">
      {/* Round header — slim now; the big real estate goes to the word/text panels below */}
      <div className="bento bento-coral p-4 md:p-5 text-white">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="min-w-0">
            <p className="eyebrow text-white/80">
              {t("play.round_header_kicker")}
            </p>
            <h2 className="headline-tight text-2xl md:text-3xl mt-1">
              {themeName} ·{" "}
              <span className="numeral">{round.base_score}</span>
            </h2>
          </div>
          <div className="flex items-center gap-3 flex-wrap justify-end">
            {/* Just the describer's name/avatar lives in the header now —
                the like/dislike controls live in the Scoreboard, attached
                to the describer's row. */}
            <DescriberBadge
              describer={describer}
              fallbackId={round.describer_id}
            />
            {settings.mode === "time" && secondsLeft !== null && (
              <CountdownChip seconds={secondsLeft} />
            )}
          </div>
        </div>
        {isHost && (
          <div className="mt-3 flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => send({ type: "round/force_end" })}
              className="btn btn-sm btn-ghost"
            >
              {t("play.force_end")}
            </button>
          </div>
        )}
      </div>

      {/* Describer / Guesser specific view */}
      {isDescriber ? (
        <DescriberPanel
          describerWord={describerWord}
          liveText={liveText}
          roomLanguage={roomLanguage}
          uiLanguage={uiLanguage}
          send={send}
        />
      ) : (
        <GuesserPanel
          describer={describer}
          liveText={liveText}
          letterPattern={round.letter_pattern ?? null}
          letterCount={round.letter_count ?? null}
          revealedIndices={round.revealed_indices ?? []}
          settings={settings}
          yourFreeAttemptsLeft={yourFreeAttemptsLeft}
          yourPaidAttemptsTotal={yourPaidAttemptsTotal}
          guessFlash={guessFlash}
          hasAlreadyGuessedCorrectly={hasAlreadyGuessedCorrectly}
          hasConceded={
            props.yourPlayerId !== null &&
            (round.conceded_player_ids ?? []).includes(props.yourPlayerId)
          }
          clearGuessFlash={clearGuessFlash}
          roomLanguage={roomLanguage}
          uiLanguage={uiLanguage}
          send={send}
        />
      )}
    </section>
  );
}

function LetterPatternStrip({
  pattern,
  letterCount,
  revealedIndices,
}: {
  pattern: string;
  letterCount: number;
  revealedIndices: number[];
}) {
  const { t } = useTranslation();
  const revealedSet = new Set(revealedIndices);
  const revealedCount = revealedSet.size;

  return (
    <div className="bento bento-yellow p-4 md:p-5">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <p className="eyebrow">{t("play.letter_pattern_label")}</p>
        <span
          className="numeral text-base md:text-lg font-bold tabular-nums"
          aria-label={t("play.letter_pattern_count_aria", {
            revealed: revealedCount,
            total: letterCount,
          })}
        >
          {revealedCount}/{letterCount}
        </span>
      </div>
      <div
        className="mt-2 font-mono text-2xl md:text-3xl tracking-[0.18em] break-words"
        aria-live="polite"
      >
        {Array.from(pattern).map((ch, i) => {
          if (ch === " ") return <span key={i}>&nbsp;&nbsp;</span>;
          if (ch === "_")
            return (
              <span key={i} className="opacity-50">
                _
              </span>
            );
          return (
            <span key={i} className="text-rouge font-bold">
              {ch}
            </span>
          );
        })}
      </div>
      <p className="mt-2 text-xs opacity-70">
        {t("play.letter_pattern_hint")}
      </p>
    </div>
  );
}

function DescriberBadge({
  describer,
  fallbackId,
}: {
  describer: PlayerPublic | null;
  fallbackId: string;
}) {
  const { t } = useTranslation();
  const name = describer?.nickname ?? fallbackId;
  const initial = (name[0] ?? "?").toUpperCase();

  return (
    <div className="inline-flex items-center gap-2.5">
      <div
        aria-hidden
        className="grid place-items-center w-9 h-9 rounded-full headline text-base bg-white/15 ring-1 ring-white/50"
      >
        {initial}
      </div>
      <div className="flex flex-col items-start leading-tight">
        <p className="eyebrow text-white/70 leading-none">
          {t("play.describer_label")}
        </p>
        <p className="headline text-lg">{name}</p>
      </div>
    </div>
  );
}

function CountdownChip({ seconds }: { seconds: number }) {
  const danger = seconds <= 10;
  return (
    <span
      className={
        "chip " +
        (danger ? "chip-coral !text-base !py-1 !px-3" : "chip-yellow !text-base !py-1 !px-3")
      }
      aria-live="polite"
    >
      ⏱ {formatSeconds(seconds)}
    </span>
  );
}

// ---------------------------------------------------------- describer

function DescriberPanel({
  describerWord,
  liveText,
  roomLanguage,
  uiLanguage,
  send,
}: {
  describerWord: DescriberWord | null;
  liveText: string;
  roomLanguage: string;
  uiLanguage: string;
  send: (event: ClientEvent) => boolean;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(liveText);
  const [hintRevealed, setHintRevealed] = useState(false);
  const localRef = useRef(true); // we own the truth while typing

  // If the server's live_text gets out of sync (e.g. after reconnect), seed
  // the local draft once. We don't want incoming describer/text echoes
  // (which never fire for the describer anyway) to clobber the user's input.
  useEffect(() => {
    if (localRef.current) {
      setDraft(liveText);
      localRef.current = false;
    }
  }, [liveText]);

  // Reset the hint reveal when the word changes (new round).
  useEffect(() => {
    setHintRevealed(false);
  }, [describerWord?.word_id]);

  const throttledSend = useThrottledCallback((text: string) => {
    send({ type: "describer/text", data: { text } });
  }, TEXT_THROTTLE_MS);

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const next = e.target.value;
    setDraft(next);
    throttledSend(next);
  }

  return (
    <div className="space-y-4">
      <div className="bento bento-yellow p-7 md:p-10">
        <p className="eyebrow">{t("play.your_word")}</p>
        <h3 className="headline-tight text-6xl md:text-8xl mt-3 break-words">
          {describerWord?.word_text ?? "…"}
        </h3>
        {describerWord && (
          <div className="mt-4">
            {hintRevealed ? (
              <p className="text-base md:text-lg leading-relaxed">
                <span className="eyebrow mr-2 align-middle">{t("play.hint")}</span>
                {describerWord.hint}
                <button
                  type="button"
                  onClick={() => setHintRevealed(false)}
                  className="ml-3 text-xs underline opacity-70 hover:opacity-100"
                >
                  {t("play.hint_hide")}
                </button>
              </p>
            ) : (
              <button
                type="button"
                onClick={() => setHintRevealed(true)}
                className="btn btn-sm btn-ghost"
              >
                💡 {t("play.hint_reveal")}
              </button>
            )}
          </div>
        )}
      </div>

      <div className="bento p-5 md:p-6">
        <label htmlFor="describer-textarea" className="eyebrow block mb-2">
          {t("play.describer_input_label")}
        </label>
        <textarea
          id="describer-textarea"
          value={draft}
          onChange={handleChange}
          rows={7}
          maxLength={2000}
          placeholder={t("play.describer_input_placeholder")}
          className="field !h-auto !text-xl leading-relaxed resize-y w-full"
          autoFocus
        />
        <p className="mt-2 text-xs text-ink-soft">
          {t("play.describer_instructions")}
        </p>
      </div>

      <TranslateBar defaultSrc={roomLanguage} defaultDst={uiLanguage} />
    </div>
  );
}

// ---------------------------------------------------------- guesser

function GuesserPanel({
  describer,
  liveText,
  letterPattern,
  letterCount,
  revealedIndices,
  settings,
  yourFreeAttemptsLeft,
  yourPaidAttemptsTotal,
  guessFlash,
  hasAlreadyGuessedCorrectly,
  hasConceded,
  clearGuessFlash,
  roomLanguage,
  uiLanguage,
  send,
}: {
  describer: PlayerPublic | null;
  liveText: string;
  letterPattern: string | null;
  letterCount: number | null;
  revealedIndices: number[];
  settings: GameSettings;
  yourFreeAttemptsLeft: number | null;
  yourPaidAttemptsTotal: number;
  guessFlash: GuessFlash | null;
  hasAlreadyGuessedCorrectly: boolean;
  hasConceded: boolean;
  clearGuessFlash: () => void;
  roomLanguage: string;
  uiLanguage: string;
  send: (event: ClientEvent) => boolean;
}) {
  const { t } = useTranslation();
  const [guess, setGuess] = useState("");
  // Auto-dismiss the wrong/penalty flash after a moment.
  useEffect(() => {
    if (!guessFlash || guessFlash.kind === "correct") return;
    const id = window.setTimeout(clearGuessFlash, 2400);
    return () => window.clearTimeout(id);
  }, [guessFlash, clearGuessFlash]);

  function submit() {
    const text = guess.trim();
    if (!text || hasAlreadyGuessedCorrectly) return;
    send({ type: "guess/submit", data: { text } });
    setGuess("");
  }

  const inAttemptsMode = settings.mode === "attempts";

  // Count the non-space characters the guesser has typed — used in the
  // "n/total" counter next to the input as a length-matching hint.
  const typedLetterCount = countLetters(guess);

  return (
    <div className="space-y-4">
      {letterPattern && letterCount !== null && letterCount > 0 && (
        <LetterPatternStrip
          pattern={letterPattern}
          letterCount={letterCount}
          revealedIndices={revealedIndices}
        />
      )}

      <div className="bento bento-mint p-7 md:p-10">
        <p className="eyebrow">
          {t("play.guesser_kicker", { describer: describer?.nickname ?? "" })}
        </p>
        <div
          className="mt-4 min-h-[8rem] md:min-h-[12rem] text-2xl md:text-3xl font-medium leading-relaxed whitespace-pre-wrap break-words"
          aria-live="polite"
          aria-atomic="false"
        >
          {liveText || (
            <span className="text-ink-soft italic">
              {t("play.guesser_idle", { describer: describer?.nickname ?? "" })}
            </span>
          )}
        </div>
      </div>

      <div className="bento p-4 md:p-5">
        {hasAlreadyGuessedCorrectly ? (
          <div className="bento bento-flat bg-white/0 p-3 text-center">
            <p className="headline text-xl">✓ {t("play.you_got_it")}</p>
            <p className="text-sm opacity-70 mt-1">
              {t("play.waiting_for_others")}
            </p>
          </div>
        ) : hasConceded ? (
          <div className="bento bento-flat bg-white/0 p-3 text-center">
            <p className="headline text-xl" style={{ color: "#c1283c" }}>
              ✕ {t("play.you_conceded")}
            </p>
            <p className="text-sm opacity-70 mt-1">
              {t("play.waiting_for_others_concede")}
            </p>
          </div>
        ) : (
          <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
            className="flex gap-2 items-center"
          >
            <input
              type="text"
              value={guess}
              onChange={(e) => setGuess(e.target.value)}
              maxLength={120}
              placeholder={t("play.guess_placeholder")}
              className="field text-lg flex-1"
              aria-label={t("play.guess_input_aria")}
              autoFocus
            />
            {letterCount !== null && letterCount > 0 && (
              <span
                className={
                  "numeral text-base md:text-lg font-bold tabular-nums shrink-0 px-2 " +
                  (typedLetterCount === letterCount
                    ? "text-emerald-700"
                    : "opacity-70")
                }
                aria-label={t("play.guess_typed_count_aria", {
                  typed: typedLetterCount,
                  total: letterCount,
                })}
                title={t("play.guess_typed_count_aria", {
                  typed: typedLetterCount,
                  total: letterCount,
                })}
              >
                {typedLetterCount}/{letterCount}
              </span>
            )}
            <button
              type="submit"
              disabled={!guess.trim()}
              className="btn btn-coral"
            >
              {t("play.guess_submit")}
            </button>
          </form>
          <div className="mt-2 text-right">
            <button
              type="button"
              onClick={() => {
                if (window.confirm(t("play.concede_confirm"))) {
                  send({ type: "round/concede" });
                }
              }}
              className="btn btn-sm btn-ghost text-xs"
            >
              ✕ {t("play.concede")}
            </button>
          </div>
          </>
        )}

        {inAttemptsMode && yourFreeAttemptsLeft !== null && (
          <div className="mt-3 flex flex-wrap gap-2 items-center">
            <span className="chip chip-yellow">
              {t("play.free_left", { n: yourFreeAttemptsLeft })}
            </span>
            {yourPaidAttemptsTotal > 0 && (
              <span className="chip chip-coral">
                {t("play.paid_used", {
                  n: yourPaidAttemptsTotal,
                  cost: yourPaidAttemptsTotal *
                    settings.scoring.penalty_per_attempt,
                })}
              </span>
            )}
          </div>
        )}

        {guessFlash && (
          <p
            className={
              "mt-3 text-sm font-medium " +
              (guessFlash.kind === "correct"
                ? "text-emerald-700"
                : guessFlash.kind === "penalty"
                  ? "text-rose-700"
                  : "text-ink-soft")
            }
            role="status"
          >
            {guessFlash.kind === "correct" && t("play.flash_correct")}
            {guessFlash.kind === "wrong" && t("play.flash_wrong")}
            {guessFlash.kind === "penalty" &&
              t("play.flash_penalty", { amount: guessFlash.amount ?? 0 })}
          </p>
        )}
      </div>

      {!hasAlreadyGuessedCorrectly && (
        <TranslateBar
          defaultSrc={roomLanguage}
          defaultDst={uiLanguage}
          onPasteToGuess={(text) => setGuess(text)}
        />
      )}
    </div>
  );
}

/** Count non-whitespace characters — matches how the round's letter_count
 * is computed on the server (which skips spaces). */
function countLetters(text: string): number {
  let n = 0;
  for (const ch of text) {
    if (!/\s/.test(ch)) n += 1;
  }
  return n;
}
