import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/http";
import { createRoom, joinRoom } from "../api/rooms";
import { RulesModal } from "../components/common/RulesModal";
import { SettingsModal } from "../components/common/SettingsModal";
import { loadNickname, saveCredentials, saveNickname } from "../lib/storage";

export default function Index() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [nickname, setNickname] = useState("");
  const [code, setCode] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [busy, setBusy] = useState<"create" | "join" | null>(null);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  // The corpus language (i.e. theme + word list) the host wants for the
  // game. Defaults to the host's UI language but is independent of it —
  // an English-UI host can run a Russian-language room and vice versa.
  const [gameLanguage, setGameLanguage] = useState<"en" | "ru">(() => {
    const ui = i18n.resolvedLanguage;
    return ui === "ru" ? "ru" : "en";
  });

  useEffect(() => {
    setNickname(loadNickname());
  }, []);

  // If the UI language changes (Settings) before the user has clicked
  // create, follow that as the new default — they're communicating intent.
  useEffect(() => {
    setGameLanguage(i18n.resolvedLanguage === "ru" ? "ru" : "en");
  }, [i18n.resolvedLanguage]);

  const trimmedNick = nickname.trim();
  const canCreate = trimmedNick.length > 0 && busy === null;
  const canJoin = trimmedNick.length > 0 && code.trim().length > 0 && busy === null;

  const errorMessage = errorCode ? t(`errors.${errorCode}`, t("errors.unknown_error")) : null;

  async function handleCreate() {
    setErrorCode(null);
    setBusy("create");
    try {
      const res = await createRoom(trimmedNick, gameLanguage);
      saveNickname(trimmedNick);
      saveCredentials(res.code, { player_id: res.player_id, token: res.token });
      navigate(`/r/${res.code}`);
    } catch (e) {
      setErrorCode(e instanceof ApiError ? e.code : "unknown_error");
    } finally {
      setBusy(null);
    }
  }

  async function handleJoin() {
    setErrorCode(null);
    setBusy("join");
    const normalised = code.trim().toUpperCase();
    try {
      const res = await joinRoom(normalised, trimmedNick);
      saveNickname(trimmedNick);
      saveCredentials(res.code, { player_id: res.player_id, token: res.token });
      navigate(`/r/${res.code}`);
    } catch (e) {
      setErrorCode(e instanceof ApiError ? e.code : "unknown_error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main id="main" tabIndex={-1} className="min-h-screen px-5 py-8 md:py-14 relative">
      <div className="mx-auto w-full max-w-3xl space-y-5 md:space-y-6">
        {/* ─── Masthead ─────────────────────────────────────────── */}
        <section className="bento bento-yellow bento-lg pop-in p-6 md:p-10 overflow-hidden" data-order="1">
          <div className="flex items-start justify-between gap-4">
            <p className="eyebrow">{t("menu.eyebrow")}</p>
            <LangToggle />
          </div>
          <h1 className="headline-tight text-[14vw] md:text-[7.2rem] mt-3 md:mt-4 break-words">
            {t("menu.title")}
          </h1>
          <p className="mt-1 text-base md:text-lg font-mono uppercase tracking-[0.18em] opacity-80">
            {t("menu.subtitle")}
          </p>
          <p className="mt-5 md:mt-7 text-lg md:text-xl font-medium max-w-xl">
            <span className="hl-coral">{t("menu.tagline_lead")}</span>{" "}
            {t("menu.tagline_tail")}
          </p>
          <span className="sticker absolute top-4 right-4 hidden md:inline-block">
            {t("menu.sticker")}
          </span>
        </section>

        {/* ─── Name ─────────────────────────────────────────────── */}
        <section className="bento pop-in p-5 md:p-6" data-order="2">
          <label htmlFor="nick" className="eyebrow block mb-2">
            {t("menu.nickname_label")}
          </label>
          <input
            id="nick"
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            placeholder={t("menu.nickname_placeholder")}
            maxLength={24}
            className="field text-xl font-semibold"
            autoComplete="off"
            autoFocus
          />
        </section>

        {/* ─── Two action cards ─────────────────────────────────── */}
        <div className="grid md:grid-cols-2 gap-5 md:gap-6">
          {/* CREATE */}
          <section
            className="bento bento-coral pop-in p-6 md:p-7 text-white"
            data-order="3"
          >
            <p className="eyebrow text-white/80">{t("menu.create_eyebrow")}</p>
            <h2 className="headline text-3xl md:text-4xl mt-2">
              {t("menu.create_heading")}
            </h2>
            <p className="mt-2 text-white/90">{t("menu.create_body")}</p>

            {/* Corpus language picker — independent of the UI language. */}
            <div className="mt-4">
              <p className="eyebrow text-white/80 mb-1.5">
                {t("menu.game_language_label")}
              </p>
              <div className="seg w-full">
                {(["en", "ru"] as const).map((code) => (
                  <button
                    key={code}
                    type="button"
                    onClick={() => setGameLanguage(code)}
                    data-active={gameLanguage === code}
                    className="seg-btn flex-1"
                    aria-pressed={gameLanguage === code}
                  >
                    {code === "en" ? "English" : "Русский"}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              onClick={handleCreate}
              disabled={!canCreate}
              className="btn btn-ghost mt-5 w-full justify-between"
            >
              <span>{t("menu.create_room")}</span>
              <span aria-hidden>→</span>
            </button>
          </section>

          {/* JOIN */}
          <section
            className="bento bento-mint pop-in p-6 md:p-7"
            data-order="4"
          >
            <p className="eyebrow">{t("menu.join_eyebrow")}</p>
            <h2 className="headline text-3xl md:text-4xl mt-2">
              {t("menu.join_heading")}
            </h2>
            <label htmlFor="code" className="sr-only">
              {t("menu.code_label")}
            </label>
            <input
              id="code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="ABCDEF"
              maxLength={6}
              className="field field-mono mt-3"
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="button"
              onClick={handleJoin}
              disabled={!canJoin}
              className="btn mt-4 w-full justify-between"
            >
              <span>{t("menu.join_room")}</span>
              <span aria-hidden>→</span>
            </button>
          </section>
        </div>

        {errorMessage && (
          <p className="alert pop-in" role="alert">
            {errorMessage}
          </p>
        )}

        {/* ─── Footer chips ─────────────────────────────────────── */}
        <footer className="pop-in flex flex-wrap items-center justify-center gap-4 pt-6" data-order="5">
          <button
            type="button"
            onClick={() => setRulesOpen(true)}
            className="chip chip-yellow wiggle-on-hover !text-base !py-2.5 !px-5 gap-2"
          >
            <span aria-hidden className="text-lg">✎</span> {t("menu.rules")}
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="chip chip-pink wiggle-on-hover !text-base !py-2.5 !px-5 gap-2"
          >
            <span aria-hidden className="text-lg">⚙</span> {t("menu.settings")}
          </button>
        </footer>
      </div>

      <RulesModal open={rulesOpen} onClose={() => setRulesOpen(false)} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </main>
  );
}

function LangToggle() {
  const { i18n } = useTranslation();
  const active = i18n.resolvedLanguage ?? "en";
  return (
    <div className="seg">
      {(["en", "ru"] as const).map((code) => (
        <button
          key={code}
          type="button"
          className="seg-btn"
          data-active={code === active}
          onClick={() => i18n.changeLanguage(code)}
          aria-pressed={code === active}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
