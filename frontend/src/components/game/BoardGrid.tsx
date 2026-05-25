import { Fragment } from "react";
import { useTranslation } from "react-i18next";

import type { BoardPublic } from "../../api/rooms";

interface Props {
  board: BoardPublic;
  canPick: boolean;
  onPick: (theme_id: string, difficulty: number) => void;
}

const CELL_COLOUR_BY_DIFFICULTY: string[] = [
  "bento-yellow",
  "bento-pink",
  "bento-mint",
  "bento-sky",
  "bento-lilac",
];

function isUsed(board: BoardPublic, theme_id: string, difficulty: number): boolean {
  return board.used.some((u) => u.theme_id === theme_id && u.difficulty === difficulty);
}

export function BoardGrid({ board, canPick, onPick }: Props) {
  const { t } = useTranslation();
  const cols = board.base_values.length;
  return (
    <section className="bento p-4 md:p-6 overflow-x-auto">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="headline text-xl md:text-2xl">{t("play.board_title")}</h2>
        <span className="eyebrow">
          {t("play.cells_used", {
            used: board.used.length,
            total: board.themes.length * board.base_values.length,
          })}
        </span>
      </div>
      <div
        className="grid gap-2 md:gap-3 min-w-[26rem]"
        style={{ gridTemplateColumns: `minmax(6rem, max-content) repeat(${cols}, minmax(0, 1fr))` }}
      >
        {/* corner + difficulty header */}
        <div />
        {board.base_values.map((value) => (
          <div
            key={value}
            className="eyebrow text-center self-end pb-1 numeral !text-base"
          >
            {value}
          </div>
        ))}

        {/* one row per theme */}
        {board.themes.map((theme) => (
          <Fragment key={theme.id}>
            <div className="flex items-center pr-2">
              <span className="headline text-base md:text-lg leading-tight">
                {theme.name}
              </span>
            </div>
            {board.base_values.map((value, idx) => {
              const difficulty = idx + 1;
              const used = isUsed(board, theme.id, difficulty);
              const clickable = canPick && !used;
              const colour = CELL_COLOUR_BY_DIFFICULTY[idx] ?? "bento-mint";
              return (
                <button
                  key={difficulty}
                  type="button"
                  disabled={!clickable}
                  onClick={() => clickable && onPick(theme.id, difficulty)}
                  aria-label={t("play.cell_label", {
                    theme: theme.name,
                    score: value,
                  })}
                  className={
                    "bento bento-sm " +
                    colour +
                    " py-4 md:py-7 px-2 flex items-center justify-center " +
                    "transition-transform transition-shadow duration-100 " +
                    (used
                      ? "opacity-30 pointer-events-none"
                      : clickable
                        ? "cursor-pointer hover:-translate-x-[1px] hover:-translate-y-[1px] hover:shadow-[4px_4px_0_var(--ink)] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
                        : "cursor-not-allowed opacity-80")
                  }
                >
                  <span
                    className={
                      "headline text-2xl md:text-4xl " +
                      (used ? "line-through" : "")
                    }
                  >
                    {value}
                  </span>
                </button>
              );
            })}
          </Fragment>
        ))}
      </div>
    </section>
  );
}
