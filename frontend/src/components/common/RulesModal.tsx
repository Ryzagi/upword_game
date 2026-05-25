import { useTranslation } from "react-i18next";

import { Modal } from "./Modal";

interface Props {
  open: boolean;
  onClose: () => void;
}

const SECTIONS = [
  { key: "basics",  accent: "yellow" as const, icon: "✦" },
  { key: "board",   accent: "mint" as const,   icon: "▦" },
  { key: "modes",   accent: "sky" as const,    icon: "⏱" },
  { key: "scoring", accent: "pink" as const,   icon: "★" },
  { key: "tools",   accent: "lilac" as const,  icon: "✎" },
  { key: "tips",    accent: "coral" as const,  icon: "✺" },
];

const ACCENT_CLASS: Record<string, string> = {
  yellow: "bento-yellow",
  mint: "bento-mint",
  sky: "bento-sky",
  pink: "bento-pink",
  lilac: "bento-lilac",
  coral: "bento-coral text-white",
};

export function RulesModal({ open, onClose }: Props) {
  const { t } = useTranslation();

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("rules.title")}
      eyebrow={t("rules.kicker")}
      accent="yellow"
      widthClass="max-w-2xl"
    >
      <div className="grid sm:grid-cols-2 gap-3">
        {SECTIONS.map(({ key, accent, icon }) => (
          <section
            key={key}
            className={"bento bento-sm p-4 " + ACCENT_CLASS[accent]}
          >
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-xl" aria-hidden>{icon}</span>
              <h3 className="headline text-lg">
                {t(`rules.${key}.heading`)}
              </h3>
            </div>
            <p className="text-sm leading-relaxed">
              {t(`rules.${key}.body`)}
            </p>
          </section>
        ))}
      </div>
      <p className="mt-5 text-center text-sm font-medium">
        {t("rules.signoff")}
      </p>
    </Modal>
  );
}
