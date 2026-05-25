import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        ink: {
          DEFAULT: "var(--ink)",
          soft: "var(--ink-soft)",
          faint: "var(--ink-faint)",
        },
        card: "var(--card)",
        yellow: "var(--yellow)",
        pink: "var(--pink)",
        mint: "var(--mint)",
        sky: "var(--sky)",
        lilac: "var(--lilac)",
        coral: {
          DEFAULT: "var(--coral)",
          deep: "var(--coral-deep)",
        },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "system-ui", "sans-serif"],
        sans: ['"Bricolage Grotesque"', "system-ui", "sans-serif"],
        mono: ['"Space Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: {
        bento: "16px",
        chip: "10px",
      },
      boxShadow: {
        bento: "5px 5px 0 var(--ink)",
        "bento-lg": "8px 8px 0 var(--ink)",
        "bento-sm": "3px 3px 0 var(--ink)",
      },
    },
  },
  plugins: [],
} satisfies Config;
