import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useSettingsStore } from "../../stores/useSettingsStore";
import type { FontSize, Theme } from "../../stores/useSettingsStore";
import { Modal } from "./Modal";

interface Props {
  open: boolean;
  onClose: () => void;
}

type Tab = "preferences" | "accessibility";

export function SettingsModal({ open, onClose }: Props) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("preferences");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("settings.title")}
      eyebrow={t("settings.kicker")}
      accent="sky"
    >
      <div className="seg w-full" style={{ background: "var(--bg)" }}>
        <button
          type="button"
          className="seg-btn flex-1"
          data-active={tab === "preferences"}
          onClick={() => setTab("preferences")}
        >
          {t("settings.preferences")}
        </button>
        <button
          type="button"
          className="seg-btn flex-1"
          data-active={tab === "accessibility"}
          onClick={() => setTab("accessibility")}
        >
          {t("settings.accessibility")}
        </button>
      </div>
      <div className="mt-5">
        {tab === "preferences" ? <Preferences /> : <Accessibility />}
      </div>
    </Modal>
  );
}

function Preferences() {
  const { t, i18n } = useTranslation();
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);

  return (
    <div className="space-y-3">
      <Row label={t("settings.language")}>
        <div className="seg">
          {(["en", "ru"] as const).map((code) => (
            <button
              key={code}
              type="button"
              className="seg-btn"
              data-active={i18n.resolvedLanguage === code}
              onClick={() => i18n.changeLanguage(code)}
            >
              {code === "en" ? "English" : "Русский"}
            </button>
          ))}
        </div>
      </Row>
      <Row label={t("settings.theme")}>
        <ChoiceRow<Theme>
          options={[
            ["light", t("settings.theme_light")],
            ["dark", t("settings.theme_dark")],
            ["auto", t("settings.theme_auto")],
          ]}
          value={theme}
          onChange={setTheme}
        />
      </Row>
    </div>
  );
}

function Accessibility() {
  const { t } = useTranslation();
  const fontSize = useSettingsStore((s) => s.fontSize);
  const setFontSize = useSettingsStore((s) => s.setFontSize);
  const highContrast = useSettingsStore((s) => s.highContrast);
  const setHighContrast = useSettingsStore((s) => s.setHighContrast);
  const reducedMotion = useSettingsStore((s) => s.reducedMotion);
  const setReducedMotion = useSettingsStore((s) => s.setReducedMotion);

  return (
    <div className="space-y-3">
      <Row label={t("settings.font_size")}>
        <ChoiceRow<FontSize>
          options={[
            ["small", "A"],
            ["normal", "A"],
            ["large", "A"],
          ]}
          value={fontSize}
          onChange={setFontSize}
          ariaLabels={{
            small: t("settings.font_size_small"),
            normal: t("settings.font_size_normal"),
            large: t("settings.font_size_large"),
          }}
          variantSizes={{ small: 12, normal: 16, large: 20 }}
        />
      </Row>
      <Row label={t("settings.high_contrast")}>
        <button
          type="button"
          onClick={() => setHighContrast(!highContrast)}
          aria-pressed={highContrast}
          className={"btn btn-sm " + (highContrast ? "btn-coral" : "btn-ghost")}
        >
          {highContrast ? "✓ " + t("settings.enabled") : t("settings.disabled")}
        </button>
      </Row>
      <Row label={t("settings.reduced_motion")}>
        <ChoiceRow<"auto" | "on" | "off">
          options={[
            ["auto", t("settings.auto_system")],
            ["on", t("settings.enabled")],
            ["off", t("settings.disabled")],
          ]}
          value={reducedMotion === null ? "auto" : reducedMotion ? "on" : "off"}
          onChange={(v) =>
            setReducedMotion(v === "auto" ? null : v === "on")
          }
        />
      </Row>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bento bento-sm flex items-center justify-between gap-4 px-4 py-3" style={{ background: "var(--bg)" }}>
      <span className="font-semibold">{label}</span>
      <div>{children}</div>
    </div>
  );
}

function ChoiceRow<T extends string>({
  options,
  value,
  onChange,
  ariaLabels,
  variantSizes,
}: {
  options: ReadonlyArray<readonly [T, string]>;
  value: T;
  onChange: (v: T) => void;
  ariaLabels?: Partial<Record<T, string>>;
  variantSizes?: Partial<Record<T, number>>;
}) {
  return (
    <div className="seg">
      {options.map(([opt, label]) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className="seg-btn"
          data-active={value === opt}
          aria-label={ariaLabels?.[opt]}
          style={
            variantSizes?.[opt]
              ? { fontSize: `${variantSizes[opt]}px`, lineHeight: 1 }
              : undefined
          }
        >
          {label}
        </button>
      ))}
    </div>
  );
}
