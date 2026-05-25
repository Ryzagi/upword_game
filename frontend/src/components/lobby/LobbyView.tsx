import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  GameSettings,
  PlayerPublic,
  TeamPublic,
  ThemeRef,
} from "../../api/rooms";
import type { ClientEvent } from "../../ws/events";
import { GameSettingsPanel } from "./GameSettingsPanel";
import { TeamPanel } from "./TeamPanel";
import { ThemeSelectorPanel } from "./ThemeSelectorPanel";

interface Props {
  isHost: boolean;
  yourPlayerId: string | null;
  hostId: string | null;
  players: PlayerPublic[];
  teams: TeamPublic[];
  settings: GameSettings;
  send: (event: ClientEvent) => boolean;
  yourPlayer: PlayerPublic | null;
  corpusThemes: ThemeRef[];
  maxThemePicksPerPlayer: number;
  startGameDisabledReason: string | null;
  onStartGame: () => void;
}

export function LobbyView({
  isHost,
  yourPlayerId,
  hostId,
  players,
  teams,
  settings,
  send,
  yourPlayer,
  corpusThemes,
  maxThemePicksPerPlayer,
  startGameDisabledReason,
  onStartGame,
}: Props) {
  const { t } = useTranslation();
  const [editingNickname, setEditingNickname] = useState(false);

  return (
    <>
      <div className="grid md:grid-cols-12 gap-5 md:gap-6">
        {/* Roster */}
        <section className="bento pop-in p-5 md:p-6 md:col-span-5" data-order="2">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="headline text-2xl">{t("lobby.roster")}</h2>
            <span className="chip chip-yellow">
              {t("lobby.players_count", { count: players.length })}
            </span>
          </div>
          <ul className="space-y-2">
            {players.map((p) => {
              const isYou = p.id === yourPlayerId;
              const isEditing = isYou && editingNickname;
              return (
                <li
                  key={p.id}
                  className="flex items-center justify-between gap-3 py-2 border-b-2 border-dotted last:border-b-0"
                  style={{ borderColor: "var(--ink)" }}
                >
                  <span className="flex items-center gap-2 min-w-0 flex-1">
                    <span
                      aria-hidden
                      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                      style={{
                        background: p.is_connected ? "var(--mint)" : "var(--ink-faint)",
                        border: "2px solid var(--ink)",
                      }}
                    />
                    {isEditing && yourPlayer ? (
                      <NicknameInlineEditor
                        currentNickname={yourPlayer.nickname}
                        onSubmit={(nickname) => {
                          send({ type: "lobby/rename", data: { nickname } });
                          setEditingNickname(false);
                        }}
                        onCancel={() => setEditingNickname(false)}
                      />
                    ) : (
                      <>
                        <span
                          className={
                            "font-semibold text-lg truncate " +
                            (isYou
                              ? "underline decoration-coral decoration-4 underline-offset-4"
                              : "")
                          }
                        >
                          {p.nickname}
                        </span>
                        {isYou && (
                          <button
                            type="button"
                            onClick={() => setEditingNickname(true)}
                            className="icon-btn shrink-0"
                            aria-label={t("lobby.nickname_edit_aria")}
                            title={t("lobby.nickname_edit_aria")}
                          >
                            ✎
                          </button>
                        )}
                      </>
                    )}
                  </span>
                  {!isEditing && (
                    <span className="flex items-center gap-1.5 shrink-0">
                      {isYou && (
                        <span className="chip chip-mint !text-[0.6rem] !py-0.5">
                          {t("lobby.you_marker_chip")}
                        </span>
                      )}
                      {p.id === hostId && (
                        <span className="chip chip-coral !text-[0.6rem] !py-0.5">
                          {t("lobby.host_badge")}
                        </span>
                      )}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>

        {/* Teams */}
        <div className="md:col-span-7 pop-in" data-order="3">
          <TeamPanel
            isHost={isHost}
            yourPlayerId={yourPlayerId}
            players={players}
            teams={teams}
            settings={settings}
            send={send}
          />
        </div>
      </div>

      {/* Game settings + Theme picker */}
      <div className="grid md:grid-cols-12 gap-5 md:gap-6">
        <div className="md:col-span-7 pop-in" data-order="4">
          <GameSettingsPanel isHost={isHost} settings={settings} send={send} />
        </div>

        <div className="md:col-span-5 pop-in" data-order="5">
          <ThemeSelectorPanel
            yourPlayer={yourPlayer}
            players={players}
            corpusThemes={corpusThemes}
            maxPicks={maxThemePicksPerPlayer}
            send={send}
          />
        </div>
      </div>

      {/* Start game CTA — host only */}
      {isHost && (
        <section
          className="bento bento-lg bento-coral pop-in p-6 md:p-7 text-white flex items-center justify-between gap-4 flex-wrap"
          data-order="6"
        >
          <div>
            <p className="eyebrow text-white/80">{t("lobby.start_kicker")}</p>
            <h2 className="headline text-2xl md:text-3xl mt-1">
              {t("lobby.start_heading")}
            </h2>
            {startGameDisabledReason && (
              <p className="text-white/90 text-sm mt-1">
                {startGameDisabledReason}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onStartGame}
            disabled={startGameDisabledReason !== null}
            className="btn btn-ghost text-lg px-6 py-3"
          >
            {t("lobby.start")} →
          </button>
        </section>
      )}
    </>
  );
}

function NicknameInlineEditor({
  currentNickname,
  onSubmit,
  onCancel,
}: {
  currentNickname: string;
  onSubmit: (next: string) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(currentNickname);

  useEffect(() => {
    setDraft(currentNickname);
  }, [currentNickname]);

  const trimmed = draft.trim();
  const canSubmit = trimmed.length > 0 && trimmed !== currentNickname;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit(trimmed);
        else onCancel();
      }}
      className="flex gap-1.5 items-center min-w-0 flex-1"
    >
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onCancel();
        }}
        maxLength={24}
        autoFocus
        className="field font-semibold !py-1 !px-2 !text-base flex-1 min-w-0"
      />
      <button
        type="submit"
        disabled={!canSubmit}
        className="icon-btn shrink-0"
        aria-label={t("lobby.save")}
        title={t("lobby.save")}
      >
        ✓
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="icon-btn shrink-0"
        aria-label={t("menu.cancel")}
        title={t("menu.cancel")}
      >
        ✕
      </button>
    </form>
  );
}
