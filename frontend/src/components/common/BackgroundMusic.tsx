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
 *
 * When anything goes wrong (404, decode failure, autoplay denied) we
 * surface a small "tap to start music" pill in the corner so the user has
 * a single clear action to recover.
 */
export function BackgroundMusic() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const musicVolume = useSettingsStore((s) => s.musicVolume);
  const [unlocked, setUnlocked] = useState(false);
  const [needsUserAction, setNeedsUserAction] = useState(false);
  const [errorReason, setErrorReason] = useState<string | null>(null);

  // Keep the live audio element's volume in sync once unmuted.
  useEffect(() => {
    const el = audioRef.current;
    if (!el || !unlocked) return;
    el.volume = Math.max(0, Math.min(1, musicVolume / 100));
  }, [musicVolume, unlocked]);

  function startPlayback(viaUserGesture: boolean): void {
    const el = audioRef.current;
    if (!el) return;
    el.muted = false;
    const targetVolume = Math.max(
      0,
      Math.min(1, useSettingsStore.getState().musicVolume / 100)
    );
    // Gentle fade-in over ~400ms so the unmute isn't jarring.
    const start = performance.now();
    const FADE_MS = 400;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / FADE_MS);
      el.volume = targetVolume * t;
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);

    const p = el.play();
    if (p && typeof p.catch === "function") {
      p.catch((err) => {
        if (!viaUserGesture) {
          // First attempt (autoplay) — surface the prompt.
          setNeedsUserAction(true);
        } else {
          // User just clicked and it still failed — log loudly.
          // eslint-disable-next-line no-console
          console.warn("[BackgroundMusic] play() failed:", err);
          setErrorReason(String(err?.name || err || "play_failed"));
        }
      });
    }
    setUnlocked(true);
    setNeedsUserAction(false);
  }

  // Muted autoplay on mount + interaction unlock.
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;

    let cancelled = false;

    // Surface load errors visibly so we don't silently fail.
    const onLoadError = () => {
      // eslint-disable-next-line no-console
      console.warn("[BackgroundMusic] audio failed to load:", el.error);
      setErrorReason("load_failed");
      setNeedsUserAction(true);
    };
    el.addEventListener("error", onLoadError);

    // Start muted — every modern browser allows this without a gesture.
    el.muted = true;
    el.volume = 0;
    const startPromise = el.play();
    if (startPromise && typeof startPromise.catch === "function") {
      startPromise.catch(() => {
        // Even muted autoplay was denied — we need the user to tap.
        if (!cancelled) setNeedsUserAction(true);
      });
    }

    const unlock = () => {
      removeUnlockers();
      startPlayback(true);
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
      cancelled = true;
      removeUnlockers();
      el.removeEventListener("error", onLoadError);
      el.pause();
    };
    // We deliberately ignore `unlocked` in deps — the effect must only
    // run once on mount; subsequent volume changes are handled above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // If the user's volume is 0, hide the prompt — they explicitly muted.
  const muted = musicVolume === 0;
  const showPrompt = needsUserAction && !unlocked && !muted;

  return (
    <>
      <audio
        ref={audioRef}
        src={MUSIC_URL}
        loop
        preload="auto"
        playsInline
        aria-hidden
      />
      {showPrompt && (
        <button
          type="button"
          onClick={() => startPlayback(true)}
          className="fixed bottom-4 right-4 z-50 chip chip-yellow !py-2 !px-3 shadow-lg cursor-pointer"
          aria-label="Start background music"
          title={errorReason ? `audio: ${errorReason}` : undefined}
        >
          <span aria-hidden className="text-base">🎵</span>
          <span className="ml-1.5">Tap to start music</span>
        </button>
      )}
    </>
  );
}
