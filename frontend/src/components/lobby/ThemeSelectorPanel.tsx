import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { PlayerPublic, ThemeRef } from "../../api/rooms";
import { useRoomStore } from "../../stores/useRoomStore";
import type { ClientEvent } from "../../ws/events";

const COOLDOWN_SECONDS = 30;
// Must match MAX_GENERATED_THEMES_PER_PLAYER in backend/app/rooms/room.py.
const PLAYER_GEN_CAP = 2;
// Must match MAX_GENERATED_THEMES_PER_ROOM in backend/app/rooms/room.py.
const ROOM_GEN_CAP = 20;
// Must match MAX_PROMPT_LENGTH in backend/app/ai/theme_generator.py.
const PROMPT_MAX_LENGTH = 400;

interface Props {
  yourPlayer: PlayerPublic | null;
  players: PlayerPublic[];
  corpusThemes: ThemeRef[];
  maxPicks: number;
  /** Per-player generation count for the current lobby session
   *  (player_id -> count). Resets when the room returns to the lobby, so
   *  each game grants a fresh allowance. */
  themeGenUsed: Record<string, number>;
  /** Whether the current player is the host (can manage any generated
   *  theme, not just their own). */
  isHost: boolean;
  send: (event: ClientEvent) => boolean;
}

export function ThemeSelectorPanel({
  yourPlayer,
  players,
  corpusThemes,
  maxPicks,
  themeGenUsed,
  isHost,
  send,
}: Props) {
  const { t } = useTranslation();
  // Theme id currently being re-rolled (shows a spinner, disables actions).
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  // When the corpus list changes (regenerate resolved → theme_regenerated),
  // clear the in-flight spinner.
  useEffect(() => {
    setRegeneratingId(null);
  }, [corpusThemes]);

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
  // Per-player generation count for THIS lobby session — comes from the
  // server (resets on play_again) rather than counting attributed themes,
  // which persist across games. That's what lets each new game grant a
  // fresh allowance while the old themes remain pickable.
  const yourGeneratedCount = yourPlayer
    ? (themeGenUsed[yourPlayer.id] ?? 0)
    : 0;
  const totalGeneratedCount = corpusThemes.filter((t) => t.generated_by).length;
  const playerCapReached = yourGeneratedCount >= PLAYER_GEN_CAP;
  const roomCapReached = totalGeneratedCount >= ROOM_GEN_CAP;
  const capReached = playerCapReached || roomCapReached;

  function toggle(themeId: string) {
    if (!yourPlayer) return;
    const has = yourPickSet.has(themeId);
    let next: string[];
    if (has) {
      next = yourPicks.filter((id) => id !== themeId);
    } else if (yourPicks.length >= maxPicks) {
      // Cap reached — no-op.
      return;
    } else {
      next = [...yourPicks, themeId];
    }
    send({ type: "lobby/theme_picks_set", data: { theme_ids: next } });
  }

  const atMax = yourPicks.length >= maxPicks;
  // Cap is uniform at 2 picks per player regardless of room size.
  const subtitle = t("lobby.themes.subtitle_two");

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
        yourGeneratedCount={yourGeneratedCount}
        playerCapReached={playerCapReached}
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
            // Generated themes can be deleted / re-rolled by their creator
            // or the host.
            const isGenerated = !!generatorId;
            const canManage =
              isGenerated &&
              !!yourPlayer &&
              (generatorId === yourPlayer.id || isHost);
            const isRegenerating = regeneratingId === theme.id;
            const tooltip = claimed
              ? t("lobby.themes.claimed_by", { name: ownerName })
              : atCap
                ? t("lobby.themes.max_reached", { count: maxPicks })
                : generatorName
                  ? t("lobby.themes.generated_by", { name: generatorName })
                  : theme.surprise
                    ? t("lobby.themes.surprise_hint")
                    : undefined;
            return (
              <li key={theme.id} className="inline-flex items-center">
                <button
                  type="button"
                  onClick={() => toggle(theme.id)}
                  disabled={disabled || isRegenerating}
                  title={tooltip}
                  className={
                    "chip-toggle " +
                    (selected
                      ? "chip-toggle-on"
                      : claimed
                        ? "chip-toggle-claimed"
                        : "chip-toggle-off") +
                    (canManage ? " !rounded-r-none" : "") +
                    (disabled && !claimed ? " opacity-40 cursor-not-allowed" : "")
                  }
                  aria-pressed={selected}
                  aria-disabled={disabled || undefined}
                >
                  {theme.surprise && (
                    <span aria-hidden className="mr-0.5">
                      🎲
                    </span>
                  )}
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
                {canManage && (
                  <span className="inline-flex">
                    <button
                      type="button"
                      onClick={() => {
                        if (isRegenerating) return;
                        setRegeneratingId(theme.id);
                        send({
                          type: "lobby/theme_regenerate",
                          data: { theme_id: theme.id },
                        });
                      }}
                      disabled={isRegenerating}
                      title={t("lobby.themes.regenerate")}
                      aria-label={t("lobby.themes.regenerate")}
                      className="theme-action"
                    >
                      <span className={isRegenerating ? "inline-block animate-spin" : ""}>
                        ⟳
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (isRegenerating) return;
                        if (window.confirm(t("lobby.themes.delete_confirm", { name: theme.name }))) {
                          send({
                            type: "lobby/theme_delete",
                            data: { theme_id: theme.id },
                          });
                        }
                      }}
                      disabled={isRegenerating}
                      title={t("lobby.themes.delete")}
                      aria-label={t("lobby.themes.delete")}
                      className="theme-action theme-action-danger !rounded-r-full"
                    >
                      ✕
                    </button>
                  </span>
                )}
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

// Approximate end-to-end generation time for a single happy-path call.
// The progress bar fills to ~90% over this duration, then lingers there
// until the response actually arrives. Tuned empirically: a clean call
// with no retries is ~5-10s; a 3-attempt retry can take ~25s.
const GEN_EXPECTED_MS = 12_000;
// How long to leave the bar at 100% after success before hiding it.
const GEN_FINAL_SNAP_MS = 600;

function GeneratorForm({
  send,
  capReached,
  yourGeneratedCount,
  playerCapReached,
}: {
  send: (event: ClientEvent) => boolean;
  capReached: boolean;
  yourGeneratedCount: number;
  playerCapReached: boolean;
}) {
  const { t } = useTranslation();
  const [prompt, setPrompt] = useState("");
  const [inFlight, setInFlight] = useState(false);
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const [progress, setProgress] = useState(0);
  const lastError = useRoomStore((s) => s.lastError);
  const corpusThemes = useRoomStore((s) => s.corpusThemes);

  // When our optimistic in-flight request resolves (either by a new theme
  // landing in corpusThemes or an error showing up), drop the spinner +
  // start the cooldown timer.
  useEffect(() => {
    if (!inFlight) return;
    setInFlight(false);
    setProgress(1); // snap to full on success
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
      setProgress(0);
    }
  }, [lastError, inFlight]);

  // Drive the progress bar with rAF while a generation is in flight.
  // Fills 0 → 0.9 over GEN_EXPECTED_MS and then lingers at 0.9 until the
  // request resolves (when success snaps it to 1.0 via the effect above).
  useEffect(() => {
    if (!inFlight) return;
    const started = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const elapsed = now - started;
      const t = Math.min(0.9, elapsed / GEN_EXPECTED_MS);
      setProgress(t);
      if (inFlight) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inFlight]);

  // After we snap to 100% on success, fade the bar away.
  useEffect(() => {
    if (progress < 1) return;
    const id = window.setTimeout(() => setProgress(0), GEN_FINAL_SNAP_MS);
    return () => window.clearTimeout(id);
  }, [progress]);

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

  const buttonLabel = playerCapReached
    ? t("lobby.themes.gen_player_cap_reached", {
        count: yourGeneratedCount,
        max: PLAYER_GEN_CAP,
      })
    : capReached
      ? t("lobby.themes.gen_room_cap_reached", { max: ROOM_GEN_CAP })
      : inFlight
        ? t("lobby.themes.gen_in_flight")
        : onCooldown
          ? t("lobby.themes.gen_cooldown", { seconds: cooldownLeft })
          : `✨ ${t("lobby.themes.gen_action")}`;

  const charsLeft = PROMPT_MAX_LENGTH - prompt.length;
  const showCounter = prompt.length >= PROMPT_MAX_LENGTH - 30;

  const showProgress = progress > 0;

  return (
    <div className="mb-4">
    <form onSubmit={submit} className="flex gap-2">
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
    {showProgress && (
      <div
        className="mt-2 h-1.5 w-full overflow-hidden rounded-full border-2 border-ink"
        style={{ background: "var(--card)" }}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress * 100)}
        aria-label={t("lobby.themes.gen_in_flight")}
      >
        <div
          className="h-full"
          style={{
            width: `${progress * 100}%`,
            background: "var(--coral)",
            transition:
              progress >= 1 ? "width 200ms ease-out" : "width 120ms linear",
          }}
        />
      </div>
    )}
    </div>
  );
}
