import { useEffect, useRef } from "react";

import { useSettingsStore } from "../../stores/useSettingsStore";

const MUSIC_URL = "/api/music/background-music.mp3";

/**
 * Looping background music. Mounted once at the app root. Volume tracks the
 * persisted setting in real time; 0 mutes (but the audio element stays
 * loaded so resuming is instant).
 *
 * Browsers block autoplay until the user has interacted with the page.
 * We try to start immediately and, if that's rejected, attach one-shot
 * listeners that retry on the first click/keypress/touch — at which point
 * autoplay is permanently unlocked for the session.
 */
export function BackgroundMusic() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const musicVolume = useSettingsStore((s) => s.musicVolume);

  // Keep the live audio element in sync with the slider.
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    el.volume = Math.max(0, Math.min(1, musicVolume / 100));
  }, [musicVolume]);

  // Autoplay-with-fallback.
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;

    let unlocked = false;

    const tryPlay = () => {
      if (unlocked) return;
      const p = el.play();
      if (p && typeof p.then === "function") {
        p.then(() => {
          unlocked = true;
          removeUnlockers();
        }).catch(() => {
          // Still blocked — wait for an interaction.
        });
      }
    };

    const onInteraction = () => {
      tryPlay();
    };

    const removeUnlockers = () => {
      window.removeEventListener("pointerdown", onInteraction);
      window.removeEventListener("keydown", onInteraction);
      window.removeEventListener("touchstart", onInteraction);
    };

    tryPlay();
    window.addEventListener("pointerdown", onInteraction);
    window.addEventListener("keydown", onInteraction);
    window.addEventListener("touchstart", onInteraction);

    return () => {
      removeUnlockers();
      el.pause();
    };
  }, []);

  return (
    <audio
      ref={audioRef}
      src={MUSIC_URL}
      loop
      preload="auto"
      // Hidden — we control via Settings.
      aria-hidden
    />
  );
}
