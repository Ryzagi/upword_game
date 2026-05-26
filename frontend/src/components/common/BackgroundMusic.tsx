import { useEffect, useRef, useState } from "react";

import { useSettingsStore } from "../../stores/useSettingsStore";

const MUSIC_URL = "/api/music/background-music.mp3";

/**
 * Looping background music. Mounted once at the app root.
 *
 * Browser autoplay reality:
 *   • Audible autoplay is blocked everywhere without a user gesture
 *     (Chrome, Safari, Firefox all enforce this — there is no flag we can
 *     set to bypass it for first-time visitors).
 *   • MUTED autoplay IS allowed. So we start muted immediately, which gets
 *     the stream playing and the decoder warm. The instant the user
 *     interacts (click, keypress, scroll), we unmute and fade to the
 *     configured volume — no perceptible delay.
 *   • Returning visitors with prior interaction (Chrome's Media Engagement
 *     Index) often get audible autoplay on subsequent loads automatically.
 */
export function BackgroundMusic() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const musicVolume = useSettingsStore((s) => s.musicVolume);
  const [unlocked, setUnlocked] = useState(false);

  // Keep the live audio element's volume in sync once unmuted.
  useEffect(() => {
    const el = audioRef.current;
    if (!el || !unlocked) return;
    el.volume = Math.max(0, Math.min(1, musicVolume / 100));
  }, [musicVolume, unlocked]);

  // Muted autoplay on mount + interaction unlock.
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;

    // Start muted — every modern browser allows this without a gesture.
    el.muted = true;
    el.volume = 0;
    const startPromise = el.play();
    if (startPromise && typeof startPromise.catch === "function") {
      startPromise.catch(() => {
        /* If even muted autoplay was denied, we still try again on
           interaction below. */
      });
    }

    const unlock = () => {
      if (unlocked) return;
      el.muted = false;
      const targetVolume =
        Math.max(0, Math.min(1, useSettingsStore.getState().musicVolume / 100));
      // Gentle fade-in over ~400ms so the unmute isn't jarring.
      const start = performance.now();
      const FADE_MS = 400;
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / FADE_MS);
        el.volume = targetVolume * t;
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);

      // If the muted autoplay was previously rejected, play() now while
      // we're inside a user gesture.
      const p = el.play();
      if (p && typeof p.catch === "function") p.catch(() => {});

      setUnlocked(true);
      removeUnlockers();
    };

    const removeUnlockers = () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
      window.removeEventListener("touchstart", unlock);
      window.removeEventListener("scroll", unlock);
    };

    window.addEventListener("pointerdown", unlock);
    window.addEventListener("keydown", unlock);
    window.addEventListener("touchstart", unlock);
    window.addEventListener("scroll", unlock, { passive: true });

    return () => {
      removeUnlockers();
      el.pause();
    };
    // We deliberately ignore `unlocked` in deps — the effect must only
    // run once on mount; subsequent volume changes are handled above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <audio
      ref={audioRef}
      src={MUSIC_URL}
      loop
      preload="auto"
      playsInline
      aria-hidden
    />
  );
}
