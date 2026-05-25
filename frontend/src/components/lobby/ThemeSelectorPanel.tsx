import { useTranslation } from "react-i18next";

import type { PlayerPublic, ThemeRef } from "../../api/rooms";
import type { ClientEvent } from "../../ws/events";

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

  // Union of every player's picks → the board the host will start with.
  const unionIds = new Set<string>();
  for (const p of players) {
    for (const id of p.theme_picks ?? []) unionIds.add(id);
  }
  const unionThemes = corpusThemes.filter((t) => unionIds.has(t.id));

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
            const tooltip = claimed
              ? t("lobby.themes.claimed_by", { name: ownerName })
              : atCap
                ? t("lobby.themes.max_reached", { count: maxPicks })
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
