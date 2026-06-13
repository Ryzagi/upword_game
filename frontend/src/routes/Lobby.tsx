import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import type { GameSettings, PlayerPublic, TeamPublic } from "../api/rooms";
import { ApiError } from "../api/http";
import { joinRoom } from "../api/rooms";
import { RulesModal } from "../components/common/RulesModal";
import { SettingsModal } from "../components/common/SettingsModal";
import { EndedView } from "../components/game/EndedView";
import { PlayView } from "../components/game/PlayView";
import { RoundSummaryModal } from "../components/game/RoundSummaryModal";
import { LobbyView } from "../components/lobby/LobbyView";
import {
  clearCredentials,
  loadCredentials,
  loadNickname,
  saveCredentials,
  saveNickname,
} from "../lib/storage";
import { useConnectionStore } from "../stores/useConnectionStore";
import { useRoomStore } from "../stores/useRoomStore";
import { WsClient } from "../ws/client";
import type { ClientEvent } from "../ws/events";

export default function Lobby() {
  const { code: rawCode } = useParams();
  const code = (rawCode ?? "").toUpperCase();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [credentials, setCredentials] = useState(() =>
    code ? loadCredentials(code) : null
  );

  if (!code) {
    return <Centred>{t("lobby.invalid_code")}</Centred>;
  }
  if (credentials === null) {
    return (
      <JoinForm
        code={code}
        onJoined={(creds) => setCredentials(creds)}
        onCancel={() => navigate("/")}
      />
    );
  }
  return <ConnectedRoom code={code} credentials={credentials} />;
}

// ---------------------------------------------------- Join (no creds yet)

function JoinForm({
  code,
  onJoined,
  onCancel,
}: {
  code: string;
  onJoined: (creds: { player_id: string; token: string }) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [nickname, setNickname] = useState(() => loadNickname());
  const [busy, setBusy] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  async function handleJoin() {
    const trimmed = nickname.trim();
    if (!trimmed) return;
    setBusy(true);
    setErrorCode(null);
    try {
      const res = await joinRoom(code, trimmed);
      saveNickname(trimmed);
      saveCredentials(res.code, { player_id: res.player_id, token: res.token });
      onJoined({ player_id: res.player_id, token: res.token });
    } catch (e) {
      setErrorCode(e instanceof ApiError ? e.code : "unknown_error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-10 flex items-center justify-center">
      <form
        className="w-full max-w-md bento bento-mint bento-lg pop-in p-7 md:p-9"
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && nickname.trim()) handleJoin();
        }}
      >
        <p className="eyebrow">{t("lobby.knock_label")}</p>
        <h1 className="headline-tight text-5xl mt-2 flex items-baseline gap-6 md:gap-8 flex-wrap">
          <span>{t("lobby.parlour")}</span>
          <span className="font-mono tracking-[0.12em] text-4xl">{code}</span>
        </h1>
        <label htmlFor="nick" className="eyebrow block mt-6 mb-2">
          {t("menu.nickname_label")}
        </label>
        <input
          id="nick"
          type="text"
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          maxLength={24}
          className="field text-xl font-semibold"
          autoFocus
        />
        <div className="flex gap-3 mt-5">
          <button
            type="submit"
            disabled={busy || !nickname.trim()}
            className="btn btn-coral flex-1 justify-between"
          >
            <span>{t("menu.join_room")}</span>
            <span aria-hidden>→</span>
          </button>
          <button type="button" onClick={onCancel} className="btn btn-ghost">
            {t("menu.cancel")}
          </button>
        </div>
        {errorCode && (
          <p className="alert mt-4" role="alert">
            {t(`errors.${errorCode}`, t("errors.unknown_error"))}
          </p>
        )}
      </form>
    </main>
  );
}

// ------------------------------------------------- Connected: WS + room dispatch

function ConnectedRoom({
  code,
  credentials,
}: {
  code: string;
  credentials: { player_id: string; token: string };
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const wsRef = useRef<WsClient | null>(null);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [copyFlash, setCopyFlash] = useState(false);
  const [codeCopyFlash, setCodeCopyFlash] = useState(false);

  const players = useRoomStore((s) => s.players);
  const teams = useRoomStore((s) => s.teams);
  const settings = useRoomStore((s) => s.settings);
  const hostId = useRoomStore((s) => s.hostId);
  const yourPlayerId = useRoomStore((s) => s.yourPlayerId);
  const state = useRoomStore((s) => s.state);
  const board = useRoomStore((s) => s.board);
  const roomLanguage = useRoomStore((s) => s.roomLanguage);
  const corpusThemes = useRoomStore((s) => s.corpusThemes);
  const maxThemePicksPerPlayer = useRoomStore((s) => s.maxThemePicksPerPlayer);
  const themeGenUsed = useRoomStore((s) => s.themeGenUsed);
  const currentRound = useRoomStore((s) => s.currentRound);
  const currentDescriberId = useRoomStore((s) => s.currentDescriberId);
  const describerWord = useRoomStore((s) => s.describerWord);
  const liveText = useRoomStore((s) => s.liveText);
  const yourFreeAttemptsLeft = useRoomStore((s) => s.yourFreeAttemptsLeft);
  const yourPaidAttemptsTotal = useRoomStore((s) => s.yourPaidAttemptsTotal);
  const correctPlayerIds = useRoomStore((s) => s.correctPlayerIds);
  const guessFlash = useRoomStore((s) => s.guessFlash);
  const reactions = useRoomStore((s) => s.reactions);
  const chatFeed = useRoomStore((s) => s.chatFeed);
  const lastRoundResults = useRoomStore((s) => s.lastRoundResults);
  const finalScores = useRoomStore((s) => s.finalScores);
  const applyServerEvent = useRoomStore((s) => s.applyServerEvent);
  const lastError = useRoomStore((s) => s.lastError);
  const clearError = useRoomStore((s) => s.clearError);
  const clearGuessFlash = useRoomStore((s) => s.clearGuessFlash);
  const acknowledgeRoundResult = useRoomStore((s) => s.acknowledgeRoundResult);
  const resetRoom = useRoomStore((s) => s.reset);

  const status = useConnectionStore((s) => s.status);
  const closeCode = useConnectionStore((s) => s.closeCode);
  const setStatus = useConnectionStore((s) => s.setStatus);

  useEffect(() => {
    const client = new WsClient({
      code,
      token: credentials.token,
      onEvent: applyServerEvent,
      onStatusChange: setStatus,
    });
    wsRef.current = client;
    client.connect();
    return () => {
      client.close();
      wsRef.current = null;
      resetRoom();
    };
  }, [code, credentials.token, applyServerEvent, setStatus, resetRoom]);

  useEffect(() => {
    if (closeCode === 4404 || closeCode === 4401) {
      clearCredentials(code);
      navigate("/");
    }
  }, [closeCode, code, navigate]);

  const yourPlayer = useMemo(
    () => players.find((p) => p.id === yourPlayerId) ?? null,
    [players, yourPlayerId]
  );
  const isHost = yourPlayerId !== null && yourPlayerId === hostId;

  function send(event: ClientEvent): boolean {
    return wsRef.current?.send(event) ?? false;
  }
  function leave() {
    const ok = window.confirm(t("lobby.leave_confirm"));
    if (!ok) return;
    clearCredentials(code);
    navigate("/");
  }
  function copyLink() {
    navigator.clipboard?.writeText(window.location.href);
    setCopyFlash(true);
    window.setTimeout(() => setCopyFlash(false), 1400);
  }
  function copyCode() {
    navigator.clipboard?.writeText(code);
    setCodeCopyFlash(true);
    window.setTimeout(() => setCodeCopyFlash(false), 1400);
  }

  const startDisabledReason = computeStartDisabledReason(
    t,
    players,
    teams,
    settings,
    state === "lobby" ? maxThemePicksPerPlayer : null
  );

  function handleStartGame() {
    if (startDisabledReason !== null) return;
    send({ type: "lobby/start_game" });
  }

  const presentCount = players.filter((p) => p.is_connected).length;
  const inPlay = state === "board" || state === "round";

  return (
    <main id="main" tabIndex={-1} className="min-h-screen px-5 py-8 md:py-12">
      <div className="mx-auto w-full max-w-5xl space-y-5 md:space-y-6">
        {/* Masthead bento */}
        <section
          className="bento bento-yellow bento-lg pop-in p-6 md:p-8 overflow-hidden relative"
          data-order="1"
        >
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="eyebrow">
                {state === "lobby"
                  ? t("lobby.masthead_kicker")
                  : state === "ended"
                    ? t("lobby.masthead_ended")
                    : t("lobby.masthead_playing")}
              </p>
              <h1 className="headline-tight text-5xl md:text-6xl mt-2 flex items-baseline gap-6 md:gap-10 flex-wrap">
                <span>{t("lobby.parlour")}</span>
                <span className="inline-flex items-center gap-2.5">
                  <span className="font-mono tracking-[0.12em] text-4xl md:text-5xl text-rouge">
                    {code}
                  </span>
                  <button
                    type="button"
                    onClick={copyCode}
                    className="icon-btn !w-7 !h-7 !text-sm self-center"
                    data-flash={codeCopyFlash || undefined}
                    aria-label={t("lobby.code_copy_aria")}
                    title={
                      codeCopyFlash
                        ? t("lobby.code_copied")
                        : t("lobby.code_copy_aria")
                    }
                  >
                    {codeCopyFlash ? "✓" : "⧉"}
                  </button>
                </span>
              </h1>
            </div>
            <div className="flex flex-col items-end gap-3">
              <span
                className="chip chip-ink !text-[0.65rem] !py-1"
                title={t("lobby.game_language_chip_aria", {
                  lang: roomLanguage.toUpperCase(),
                })}
              >
                🌐 {roomLanguage.toUpperCase()}
              </span>
              <span className="dot" data-state={status} aria-live="polite">
                {t(`lobby.connection.${status}`, status)}
              </span>
              <p className="text-sm font-medium">
                <span className="hl-coral numeral text-base">
                  {presentCount}/{players.length}
                </span>{" "}
                {t("lobby.here_now")}
              </p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={copyLink}
              className={"btn btn-sm " + (copyFlash ? "btn-mint" : "btn-ghost")}
            >
              {copyFlash ? "✓ " + t("lobby.copied") : "🔗 " + t("lobby.copy_link")}
            </button>
            <button
              type="button"
              onClick={() => setRulesOpen(true)}
              className="btn btn-sm btn-ghost"
            >
              ✎ {t("menu.rules")}
            </button>
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="btn btn-sm btn-ghost"
            >
              ⚙ {t("menu.settings")}
            </button>
            <button
              type="button"
              onClick={leave}
              className="btn btn-sm btn-coral"
            >
              {t("lobby.leave")}
            </button>
            {inPlay && isHost && (
              <span className="chip chip-pink ml-auto">
                {t("lobby.host_badge")}
              </span>
            )}
          </div>
        </section>

        {state === "lobby" && (
          <LobbyView
            isHost={isHost}
            yourPlayerId={yourPlayerId}
            hostId={hostId}
            players={players}
            teams={teams}
            settings={settings}
            send={send}
            yourPlayer={yourPlayer}
            corpusThemes={corpusThemes}
            maxThemePicksPerPlayer={maxThemePicksPerPlayer}
            themeGenUsed={themeGenUsed}
            startGameDisabledReason={startDisabledReason}
            onStartGame={handleStartGame}
          />
        )}

        {(state === "board" || state === "round") && (
          <PlayView
            state={state}
            board={board}
            currentRound={currentRound}
            currentDescriberId={currentDescriberId}
            describerWord={describerWord}
            liveText={liveText}
            yourFreeAttemptsLeft={yourFreeAttemptsLeft}
            yourPaidAttemptsTotal={yourPaidAttemptsTotal}
            correctPlayerIds={correctPlayerIds}
            lastRoundResults={lastRoundResults}
            guessFlash={guessFlash}
            reactions={reactions}
            chatFeed={chatFeed}
            roomLanguage={roomLanguage}
            uiLanguage={i18n.resolvedLanguage ?? "en"}
            players={players}
            teams={teams}
            settings={settings}
            yourPlayerId={yourPlayerId}
            isHost={isHost}
            send={send}
            clearGuessFlash={clearGuessFlash}
          />
        )}

        {state === "ended" && (
          <EndedView
            finalScores={finalScores}
            teams={teams}
            players={players}
            yourPlayerId={yourPlayerId}
            isHost={isHost}
            send={send}
          />
        )}

        {lastError && !isLobbyOnlyErrorIrrelevantNow(lastError.code, state) && (
          <p className="alert pop-in" role="alert">
            {t(`errors.${lastError.code}`, t("errors.unknown_error"))}
            <button
              type="button"
              onClick={clearError}
              className="ml-3 underline font-semibold"
            >
              {t("common.dismiss")}
            </button>
          </p>
        )}
      </div>

      <RoundSummaryModal
        open={lastRoundResults !== null}
        result={lastRoundResults}
        board={board}
        players={players}
        teams={teams}
        onClose={acknowledgeRoundResult}
      />
      <RulesModal open={rulesOpen} onClose={() => setRulesOpen(false)} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </main>
  );
}

// ---------------------------------------------- start-game gating

function computeStartDisabledReason(
  t: (key: string, opts?: Record<string, unknown>) => string,
  players: PlayerPublic[],
  teams: TeamPublic[],
  settings: GameSettings,
  maxPicksPerPlayer: number | null
): string | null {
  if (players.length < 2) {
    return t("lobby.start_disabled.not_enough_players");
  }
  if (settings.team_mode === "teams") {
    if (teams.length < 2) {
      return t("lobby.start_disabled.need_two_teams");
    }
    for (const team of teams) {
      if (team.player_ids.length === 0) {
        return t("lobby.start_disabled.empty_team", { name: team.name });
      }
    }
    for (const p of players) {
      if (p.team_id === null) {
        return t("lobby.start_disabled.unassigned_player", { name: p.nickname });
      }
    }
  }
  if (maxPicksPerPlayer !== null) {
    for (const p of players) {
      if (!p.theme_picks || p.theme_picks.length === 0) {
        return t("lobby.start_disabled.no_theme_picks", { name: p.nickname });
      }
    }
  }
  return null;
}

// Error codes that only make sense while the room is still in the lobby —
// suppress them if a stale one is lingering after the game has started, so
// rejoining players don't see "Teams aren't set up right" while the
// scoreboard is already on screen.
const LOBBY_ONLY_ERROR_CODES = new Set([
  "bad_team_config",
  "bad_theme_picks",
  "not_enough_players",
  "team_limit_exceeded",
  "team_not_found",
  "team_name_taken",
  "team_name_invalid",
  "room_not_in_lobby",
  "theme_gen_rate_limited",
  "theme_gen_cap_reached",
  "theme_gen_failed",
  "theme_gen_invalid_prompt",
  "theme_gen_unavailable",
  "theme_not_found",
  "theme_action_forbidden",
]);

function isLobbyOnlyErrorIrrelevantNow(code: string, state: string): boolean {
  return state !== "lobby" && LOBBY_ONLY_ERROR_CODES.has(code);
}

function Centred({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-xl font-semibold">{children}</p>
    </main>
  );
}
