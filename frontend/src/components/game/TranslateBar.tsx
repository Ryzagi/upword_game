import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../api/http";
import { translate } from "../../api/translate";

interface Props {
  defaultSrc?: string;
  defaultDst?: string;
  onPasteToGuess?: (text: string) => void;
}

const LANGS: ReadonlyArray<readonly [string, string]> = [
  ["en", "English"],
  ["ru", "Русский"],
  ["es", "Español"],
  ["fr", "Français"],
  ["de", "Deutsch"],
];

export function TranslateBar({ defaultSrc = "ru", defaultDst = "en", onPasteToGuess }: Props) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [src, setSrc] = useState(defaultSrc);
  // If the caller passed the same language for both sides (common when
  // roomLanguage === uiLanguage), nudge dst to the first different language
  // in LANGS — otherwise both selects would filter their twin out and
  // display whichever option happens to be first, hiding the real default.
  const [dst, setDst] = useState(() =>
    defaultDst === defaultSrc
      ? (LANGS.find(([code]) => code !== defaultSrc)?.[0] ?? defaultDst)
      : defaultDst
  );
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function doTranslate() {
    const trimmed = text.trim();
    if (!trimmed) return;
    setBusy(true);
    setErrorCode(null);
    setResult(null);
    try {
      const r = await translate(trimmed, src, dst);
      setResult(r.translated);
    } catch (e) {
      setErrorCode(e instanceof ApiError ? e.code : "unknown_error");
    } finally {
      setBusy(false);
    }
  }

  async function copyResult() {
    if (!result) return;
    try {
      await navigator.clipboard?.writeText(result);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      /* ignore */
    }
  }

  function swap() {
    setSrc(dst);
    setDst(src);
    if (result) {
      setText(result);
      setResult(null);
    }
  }

  return (
    <div className="bento bento-sky p-4 md:p-5 space-y-3">
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <p className="eyebrow">{t("play.translate_kicker")}</p>
        <div className="flex items-center gap-2 text-sm">
          <select
            value={src}
            onChange={(e) => setSrc(e.target.value)}
            className="border-2 border-ink rounded px-2 py-1 bg-card"
            aria-label={t("play.translate_src_label")}
          >
            {LANGS.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={swap}
            className="btn btn-sm btn-ghost"
            aria-label={t("play.translate_swap_aria")}
            title={t("play.translate_swap_aria")}
          >
            ⇄
          </button>
          <select
            value={dst}
            onChange={(e) => setDst(e.target.value)}
            className="border-2 border-ink rounded px-2 py-1 bg-card"
            aria-label={t("play.translate_dst_label")}
          >
            {LANGS.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          placeholder={t("play.translate_placeholder")}
          className="field flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              doTranslate();
            }
          }}
        />
        <button
          type="button"
          onClick={doTranslate}
          disabled={busy || !text.trim() || src === dst}
          className="btn btn-coral"
        >
          {busy ? t("play.translate_busy") : t("play.translate_action")}
        </button>
      </div>

      {result && (
        <div className="bento bento-flat bg-bg p-3 space-y-2">
          <p className="text-lg font-medium">{result}</p>
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={copyResult}
              className={"btn btn-sm " + (copied ? "btn-mint" : "btn-ghost")}
            >
              {copied ? "✓ " + t("play.translate_copied") : t("play.translate_copy")}
            </button>
            {onPasteToGuess && (
              <button
                type="button"
                onClick={() => onPasteToGuess(result)}
                className="btn btn-sm btn-yellow"
              >
                {t("play.translate_paste_to_guess")} →
              </button>
            )}
          </div>
        </div>
      )}

      {errorCode && (
        <p className="alert" role="alert">
          {t(`errors.${errorCode}`, t("errors.unknown_error"))}
        </p>
      )}
    </div>
  );
}
