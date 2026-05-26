import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "light" | "dark" | "auto";
export type FontSize = "small" | "normal" | "large";

interface SettingsState {
  theme: Theme;
  fontSize: FontSize;
  highContrast: boolean;
  // null = follow system; otherwise explicit override
  reducedMotion: boolean | null;
  // Background music volume, 0..100. 0 = muted.
  musicVolume: number;

  setTheme: (t: Theme) => void;
  setFontSize: (s: FontSize) => void;
  setHighContrast: (v: boolean) => void;
  setReducedMotion: (v: boolean | null) => void;
  setMusicVolume: (v: number) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: "auto",
      fontSize: "normal",
      highContrast: false,
      reducedMotion: null,
      musicVolume: 25,

      setTheme: (t) => set({ theme: t }),
      setFontSize: (s) => set({ fontSize: s }),
      setHighContrast: (v) => set({ highContrast: v }),
      setReducedMotion: (v) => set({ reducedMotion: v }),
      setMusicVolume: (v) => set({ musicVolume: Math.max(0, Math.min(100, v)) }),
    }),
    { name: "app.settings" }
  )
);

/**
 * Imperatively reflect the current settings onto <html>. Call once at app
 * bootstrap and on every settings change. Idempotent.
 */
export function applySettingsToDom(state: SettingsState): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;

  // Theme
  const prefersDark =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  const effectiveDark = state.theme === "dark" || (state.theme === "auto" && prefersDark);
  root.classList.toggle("dark", effectiveDark);

  // Font size — Tailwind's defaults assume 16px on <html>.
  const fontSizePx = state.fontSize === "small" ? 14 : state.fontSize === "large" ? 18 : 16;
  root.style.fontSize = `${fontSizePx}px`;

  // High contrast
  root.classList.toggle("hc", state.highContrast);

  // Reduced motion
  const systemReduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const effectiveReduced =
    state.reducedMotion === null ? systemReduced : state.reducedMotion;
  root.classList.toggle("rm", effectiveReduced);
}
