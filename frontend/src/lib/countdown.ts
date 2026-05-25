import { useEffect, useState } from "react";

/**
 * Returns seconds remaining until `endsAt`, or null if unlimited / not set.
 * Ticks every 250ms for smooth display.
 */
export function useCountdown(endsAt: string | null | undefined): number | null {
  const [seconds, setSeconds] = useState<number | null>(() => compute(endsAt));

  useEffect(() => {
    if (!endsAt) {
      setSeconds(null);
      return;
    }
    setSeconds(compute(endsAt));
    const id = window.setInterval(() => setSeconds(compute(endsAt)), 250);
    return () => window.clearInterval(id);
  }, [endsAt]);

  return seconds;
}

function compute(endsAt: string | null | undefined): number | null {
  if (!endsAt) return null;
  const target = new Date(endsAt).getTime();
  if (Number.isNaN(target)) return null;
  return Math.max(0, Math.ceil((target - Date.now()) / 1000));
}

export function formatSeconds(s: number): string {
  const mm = Math.floor(s / 60).toString();
  const ss = (s % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
}
