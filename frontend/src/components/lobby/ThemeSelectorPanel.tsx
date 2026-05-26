import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { PlayerPublic, ThemeRef } from "../../api/rooms";
import { useRoomStore } from "../../stores/useRoomStore";
import type { ClientEvent } from "../../ws/events";

const COOLDOWN_SECONDS = 30;
// Must match MAX_GENERATED_THEMES_PER_ROOM in backend/app/rooms/room.py.
const ROOM_CAP = 10;
// Must match MAX_PROMPT_LENGTH in backend/app/ai/theme_generator.py.
const PROMPT_MAX_LENGTH = 400;

interface Props {
  yourPlayer: PlayerPublic | null;
  players: PlayerPublic[];
  corpusThemes: ThemeRef[];
  maxPicks: number;
  send: (event: ClientEvent) => boolean;
}

export function ThemeSelectorPanel({
  yourPlayer,
  players,
  corpusThemes,
  maxPicks,
  send,
}: Props) {
  const { t } = useTranslation();

  const yourPicks = yourPlayer?.theme_picks ?? [];
  const yourPickSet = new Set(yourPicks);

  // Map theme_id → owner nickname (for OTHER players only). Used to disable
  // chips that someone else has already claimed.
  const claimedBy = new Map<string, string>();
  for (const p of players) {
    if (p.id === yourPlayer?.id) continue;
    for (const id of p.theme_picks ?? []) {
      claimedBy.set(id, p.nickname);
    }
  }

  // Quick lookup: which themes were AI-generated, and by whom.
  const generatorById = new Map<string, string>();
  for (const theme of corpusThemes) {
    if (theme.generated_by) generatorById.set(theme.id, theme.generated_by);
  }
  const playerById = new Map(players.map((p) => [p.id, p]));

  // Union of every player's picks → the board the host will start with.
  const unionIds = new Set<string>();
  for (const p of players) {
    for (const id of p.theme_picks ?? []) unionIds.add(id);
  }
  const unionThemes = corpusThemes.filter((t) => unionIds.has(t.id));

  // ------- AI generator state -------
  const generatedCount = corpusThemes.filter((t) => t.generated_by).length;
  const capReached = generatedCount >= ROOM_CAP;

  function toggle(themeId: string) {
    if (!yourPlayer) return;
    const has = yourPickSet.has(themeId);
    let next: string[];
    if (has) {
      next = yourPicks.filter((id) => id !== themeId);
    } else if (yourPicks.length >= maxPicks) {
      // Cap reached — replace last when max is 1; otherwise no-op.
      if (maxPicks === 1) next = [themeId];
      else return;
    } else {
      next = [...yourPicks, themeId];
    }
    send({ type: "lobby/theme_picks_set", data: { theme_ids: next } });
  }

  const atMax = yourPicks.length >= maxPicks;
  const subtitle =
    maxPicks >= 2 ? t("lobby.themes.subtitle_two") : t("lobby.themes.subtitle_one");

  return (
    <section
      className="bento bento-mint pop-in p-5 md:p-6"
      data-order="5"
      aria-labelledby="theme-selector-title"
    >
      <p className="eyebrow">{t("lobby.themes.your_picks_label")}</p>
      <h2
        id="theme-selector-title"
        className="headline text-2xl mt-1 mb-1 flex items-center gap-2.5"
      >
        <span className="marker marker-coral" aria-hidden />
        {t("lobby.themes.title")}
      </h2>
      <p className="text-sm opacity-80 mb-4">
        {subtitle}{" "}
        <span className="font-semibold numeral">
          {yourPicks.length}/{maxPicks}
        </span>
      </p>

      <GeneratorForm
        send={send}
        capReached={capReached}
        generatedCount={generatedCount}
      />

      {corpusThemes.length === 0 ? (
        <p className="text-sm opacity-70">{t("lobby.themes.empty_state")}</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {corpusThemes.map((theme) => {
            const selected = yourPickSet.has(theme.id);
            const ownerName = claimedBy.get(theme.id);
            const claimed = ownerName !== undefined;
            const atCap = !selected && atMax && maxPicks > 1;
            const disabled = claimed || atCap;
            const generatorId = generatorById.get(theme.id);
            const generatorName = generatorId
              ? playerById.get(generatorId)?.nickname
              : undefined;
            const tooltip = claimed
              ? t("lobby.themes.claimed_by", { name: ownerName })
              : atCap
                ? t("lobby.themes.max_reached", { count: maxPicks })
                : generatorName
                  ? t("lobby.themes.generated_by", { name: generatorName })
                  : undefined;
            return (
              <li key={theme.id}>
                <button
                  type="button"
                  onClick={() => toggle(theme.id)}
                  disabled={disabled}
                  title={tooltip}
                  className={
                    "chip-toggle " +
                    (selected
                      ? "chip-toggle-on"
                      : claimed
                        ? "chip-toggle-claimed"
                        : "chip-toggle-off") +
                    (disabled && !claimed ? " opacity-40 cursor-not-allowed" : "")
                  }
                  aria-pressed={selected}
                  aria-disabled={disabled || undefined}
                >
                  {generatorName && (
                    <span aria-hidden className="mr-0.5">
                      ✨
                    </span>
                  )}
                  {selected && (
                    <span aria-hidden className="mr-1">
                      ✓
                    </span>
                  )}
                  {theme.name}
                  {claimed && (
                    <span className="ml-1 opacity-80 normal-case text-[0.65rem] font-mono">
                      · {ownerName}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-5 pt-4 border-t-2 border-dotted" style={{ borderColor: "var(--ink)" }}>
        <p className="eyebrow mb-2">{t("lobby.themes.board_preview_label")}</p>
        {unionThemes.length === 0 ? (
          <p className="text-sm opacity-70">{t("lobby.themes.board_preview_empty")}</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {unionThemes.map((theme) => (
              <li
                key={theme.id}
                className="chip chip-yellow !text-xs !py-1"
                title={theme.name}
              >
                {theme.name}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

// ----------------------------------------------------- AI generator form

function GeneratorForm({
  send,
  capReached,
  generatedCount,
}: {
  send: (event: ClientEvent) => boolean;
  capReached: boolean;
  generatedCount: number;
}) {
  const { t } = useTranslation();
  const [prompt, setPrompt] = useState("");
  const [inFlight, setInFlight] = useState(false);
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const lastError = useRoomStore((s) => s.lastError);
  const corpusThemes = useRoomStore((s) => s.corpusThemes);

  // When our optimistic in-flight request resolves (either by a new theme
  // landing in corpusThemes or an error showing up), drop the spinner +
  // start the cooldown timer.
  useEffect(() => {
    if (!inFlight) return;
    setInFlight(false);
    setCooldownLeft(COOLDOWN_SECONDS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corpusThemes.length]);

  // If the server responded with an error, drop the spinner and let the
  // user retry sooner.
  useEffect(() => {
    if (!lastError || !inFlight) return;
    const code = lastError.code;
    if (
      code === "theme_gen_rate_limited" ||
      code === "theme_gen_cap_reached" ||
      code === "theme_gen_failed" ||
      code === "theme_gen_invalid_prompt" ||
      code === "theme_gen_unavailable"
    ) {
      setInFlight(false);
    }
  }, [lastError, inFlight]);

  // Tick the cooldown timer.
  useEffect(() => {
    if (cooldownLeft <= 0) return;
    const id = window.setInterval(() => {
      setCooldownLeft((s) => (s <= 1 ? 0 : s - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [cooldownLeft]);

  const onCooldown = cooldownLeft > 0;
  const trimmed = prompt.trim();
  const disabled = capReached || onCooldown || inFlight || trimmed.length === 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (disabled) return;
    send({ type: "lobby/theme_generate", data: { prompt: trimmed } });
    setInFlight(true);
    setPrompt("");
  }

  const buttonLabel = capReached
    ? t("lobby.themes.gen_cap_reached", {
        count: generatedCount,
        max: ROOM_CAP,
      })
    : inFlight
      ? t("lobby.themes.gen_in_flight")
      : onCooldown
        ? t("lobby.themes.gen_cooldown", { seconds: cooldownLeft })
        : `✨ ${t("lobby.themes.gen_action")}`;

  const charsLeft = PROMPT_MAX_LENGTH - prompt.length;
  const showCounter = prompt.length >= PROMPT_MAX_LENGTH - 30;

  return (
    <form onSubmit={submit} className="flex gap-2 mb-4">
      <div className="flex-1 relative">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={t("lobby.themes.gen_placeholder")}
          maxLength={PROMPT_MAX_LENGTH}
          disabled={capReached || inFlight}
          className="field w-full !text-sm"
          aria-label={t("lobby.themes.gen_placeholder")}
        />
        {showCounter && (
          <span
            className={
              "absolute right-2 top-1/2 -translate-y-1/2 numeral text-[0.65rem] tabular-nums " +
              (charsLeft <= 0 ? "text-rouge font-bold" : "opacity-60")
            }
          >
            {charsLeft}
          </span>
        )}
      </div>
      <button
        type="submit"
        disabled={disabled}
        className={
          "btn btn-sm shrink-0 " + (capReached ? "btn-ghost" : "btn-coral")
        }
        title={buttonLabel}
      >
        {inFlight ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="animate-spin">⟳</span>
            <span className="hidden sm:inline">{t("lobby.themes.gen_in_flight")}</span>
          </span>
        ) : (
          <span className="whitespace-nowrap">{buttonLabel}</span>
        )}
      </button>
    </form>
  );
}
