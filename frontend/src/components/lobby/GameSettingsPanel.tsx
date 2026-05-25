import { useTranslation } from "react-i18next";

import type { GameSettings } from "../../api/rooms";
import type { ClientEvent } from "../../ws/events";

interface Props {
  isHost: boolean;
  settings: GameSettings;
  send: (event: ClientEvent) => boolean;
}

const TIME_VALUES = [30, 60, 90, 120] as const;
const ATTEMPTS_PRESETS = [5, 7, 10] as const;

export function GameSettingsPanel({ isHost, settings, send }: Props) {
  const { t } = useTranslation();

  function patch(part: Partial<GameSettings>) {
    if (!isHost) return;
    send({ type: "lobby/settings_set", data: part });
  }

  const isTime = settings.mode === "time";

  return (
    <section className="bento p-5 md:p-6 h-full space-y-5">
      <div className="flex items-baseline justify-between flex-wrap gap-3">
        <h2 className="headline text-2xl flex items-center gap-2.5">
          <span className="marker marker-lilac" aria-hidden />
          {t("lobby.gamesettings.title")}
        </h2>
        {isHost ? (
          <div className="seg" style={{ background: "var(--bg)" }}>
            <button
              type="button"
              className="seg-btn"
              data-active={isTime}
              onClick={() => patch({ mode: "time" })}
            >
              ⏱ {t("lobby.gamesettings.mode_time")}
            </button>
            <button
              type="button"
              className="seg-btn"
              data-active={!isTime}
              onClick={() => patch({ mode: "attempts" })}
            >
              ⊕ {t("lobby.gamesettings.mode_attempts")}
            </button>
          </div>
        ) : (
          <span className="chip">
            {isTime
              ? t("lobby.gamesettings.mode_time")
              : t("lobby.gamesettings.mode_attempts")}
          </span>
        )}
      </div>

      {isTime ? (
        <Field label={t("lobby.gamesettings.round_time_label")}>
          <div className="flex flex-wrap gap-2">
            {TIME_VALUES.map((v) => (
              <button
                key={v}
                type="button"
                className="btn btn-sm btn-ghost min-w-[3.5rem]"
                data-active={settings.time_seconds === v}
                disabled={!isHost}
                onClick={() => patch({ time_seconds: v })}
                style={
                  settings.time_seconds === v
                    ? {
                        background: "var(--selected-bg)",
                        color: "var(--selected-fg)",
                        boxShadow:
                          "inset 0 -3px 0 var(--coral), 2px 2px 0 var(--shadow-color)",
                      }
                    : undefined
                }
              >
                {v}s
              </button>
            ))}
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              disabled={!isHost}
              onClick={() => patch({ time_seconds: null })}
              style={
                settings.time_seconds === null
                  ? {
                        background: "var(--selected-bg)",
                        color: "var(--selected-fg)",
                        boxShadow:
                          "inset 0 -3px 0 var(--coral), 2px 2px 0 var(--shadow-color)",
                      }
                  : undefined
              }
            >
              ∞ {t("lobby.gamesettings.unlimited")}
            </button>
          </div>
        </Field>
      ) : (
        <Field label={t("lobby.gamesettings.attempts_label")}>
          <div className="flex flex-wrap items-baseline gap-2">
            {ATTEMPTS_PRESETS.map((v) => (
              <button
                key={v}
                type="button"
                className="btn btn-sm btn-ghost min-w-[3rem]"
                disabled={!isHost}
                onClick={() => patch({ attempts_per_round: v })}
                style={
                  settings.attempts_per_round === v
                    ? {
                        background: "var(--selected-bg)",
                        color: "var(--selected-fg)",
                        boxShadow:
                          "inset 0 -3px 0 var(--coral), 2px 2px 0 var(--shadow-color)",
                      }
                    : undefined
                }
              >
                {v}
              </button>
            ))}
            <label className="flex items-baseline gap-2 ml-2">
              <span className="eyebrow">{t("lobby.gamesettings.custom")}</span>
              <input
                type="number"
                min={1}
                max={50}
                value={settings.attempts_per_round}
                disabled={!isHost}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (Number.isFinite(v) && v >= 1 && v <= 50) {
                    patch({ attempts_per_round: v });
                  }
                }}
                className="field !w-20 text-center font-bold"
              />
            </label>
          </div>
        </Field>
      )}

      {!isHost && (
        <p className="text-sm opacity-80 italic">
          {t("lobby.gamesettings.host_only")}
        </p>
      )}
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset>
      <legend className="eyebrow mb-2">{label}</legend>
      {children}
    </fieldset>
  );
}
