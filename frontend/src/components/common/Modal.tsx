import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  eyebrow?: string;
  accent?: "yellow" | "mint" | "pink" | "sky" | "lilac" | "coral" | "card";
  children: ReactNode;
  toolbar?: ReactNode;
  widthClass?: string;
}

const ACCENT_CLASS: Record<NonNullable<Props["accent"]>, string> = {
  yellow: "bento-yellow",
  mint: "bento-mint",
  pink: "bento-pink",
  sky: "bento-sky",
  lilac: "bento-lilac",
  coral: "bento-coral",
  card: "",
};

export function Modal({
  open,
  onClose,
  title,
  eyebrow,
  accent = "card",
  children,
  toolbar,
  widthClass,
}: Props) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previouslyFocused.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-start md:items-center justify-center p-4 md:p-8"
      style={{ background: "rgba(20, 17, 10, 0.55)" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        ref={dialogRef}
        className={
          "bento bento-lg " +
          ACCENT_CLASS[accent] +
          " pop-in w-full " +
          (widthClass ?? "max-w-xl") +
          " max-h-[90vh] flex flex-col overflow-hidden"
        }
      >
        <header className="px-6 md:px-8 pt-6 md:pt-8 pb-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
              <h2 id="modal-title" className="headline text-3xl md:text-4xl">
                {title}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="btn btn-sm btn-ghost shrink-0"
            >
              ✕
            </button>
          </div>
          {toolbar && <div className="mt-4">{toolbar}</div>}
        </header>
        <div className="px-6 md:px-8 pb-6 md:pb-8 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
