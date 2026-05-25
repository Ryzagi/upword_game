import { useCallback, useEffect, useRef } from "react";

/**
 * Throttle a callback to at most one invocation per `ms`. Trailing-edge:
 * the very latest call after a quiet window is still delivered.
 */
export function useThrottledCallback<TArgs extends unknown[]>(
  fn: (...args: TArgs) => void,
  ms: number
): (...args: TArgs) => void {
  const lastInvoked = useRef(0);
  const trailingTimer = useRef<number | null>(null);
  const latestArgs = useRef<TArgs | null>(null);
  const fnRef = useRef(fn);

  // Keep fn pointer fresh without re-creating the throttled wrapper.
  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    return () => {
      if (trailingTimer.current !== null) {
        window.clearTimeout(trailingTimer.current);
        trailingTimer.current = null;
      }
    };
  }, []);

  return useCallback(
    (...args: TArgs) => {
      latestArgs.current = args;
      const now = Date.now();
      const elapsed = now - lastInvoked.current;
      if (elapsed >= ms) {
        lastInvoked.current = now;
        fnRef.current(...args);
        return;
      }
      if (trailingTimer.current === null) {
        trailingTimer.current = window.setTimeout(() => {
          trailingTimer.current = null;
          lastInvoked.current = Date.now();
          if (latestArgs.current !== null) {
            fnRef.current(...latestArgs.current);
          }
        }, ms - elapsed);
      }
    },
    [ms]
  );
}
