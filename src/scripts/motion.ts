// The script side of the motion layer (the rest is CSS, at the end of src/styles/global.css).
// Motion is off when the visitor asks for reduced motion.

export function motionAllowed(): boolean {
  return !matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Run a DOM update as a cross-fading view transition where the browser has them; otherwise just run it. */
export function withTransition(update: () => void): void {
  if (!document.startViewTransition || !motionAllowed()) {
    update();
    return;
  }
  const transition = document.startViewTransition(update);
  // A quick second click skips the first transition, which rejects these; that's expected.
  transition.ready.catch(() => {});
  transition.finished.catch(() => {});
}

/** Restart a one-shot CSS animation on an element, e.g. the result count after a filter change. */
export function replay(el: HTMLElement, className: string): void {
  if (!motionAllowed()) return;
  el.classList.remove(className);
  void el.offsetWidth; // force a style flush so the animation starts again
  el.classList.add(className);
}

const REVEAL_STAGGER_MS = 30;
const REVEAL_STAGGER_MAX = 6;

/** Upcoming rows and month headings below the first screen fade in
 * as they scroll into view, once. Anything already on screen is left alone, so nothing blinks, and
 * without this script everything is simply there. */
function initReveal(): void {
  if (!motionAllowed() || !('IntersectionObserver' in window)) return;
  const observer = new IntersectionObserver(
    (entries) => {
      let n = 0;
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const el = entry.target as HTMLElement;
        el.style.animationDelay = `${Math.min(n++, REVEAL_STAGGER_MAX - 1) * REVEAL_STAGGER_MS}ms`;
        el.classList.replace('reveal-wait', 'reveal-in');
        observer.unobserve(el);
      }
    },
    { rootMargin: '0px 0px -8% 0px' },
  );
  for (const el of document.querySelectorAll<HTMLElement>('[data-list=upcoming] :is(.month, .row)')) {
    const top = el.getBoundingClientRect().top;
    if (el.hidden || top < innerHeight) continue;
    el.classList.add('reveal-wait');
    observer.observe(el);
  }
}

export function initMotion(): void {
  initReveal();
}
