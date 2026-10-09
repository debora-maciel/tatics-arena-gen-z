/** One-shot sound effects. Elements are cached per source so a repeated cue restarts instantly. */
const cache = new Map<string, HTMLAudioElement>();

export function playSound(src: string, volume = 0.8) {
  if (typeof Audio === "undefined") return;
  let el = cache.get(src);
  if (!el) {
    el = new Audio(src);
    el.preload = "auto";
    cache.set(src, el);
  }
  el.volume = volume;
  el.currentTime = 0;
  // Autoplay policy can reject before the first user gesture; placing a unit is a gesture, so this
  // only fires in odd cases (e.g. programmatic moves) and is safe to ignore.
  el.play().catch(() => {});
}
