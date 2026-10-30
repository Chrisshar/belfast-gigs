// The Just announced row: one line of cards that scrolls sideways, with arrow buttons either side.
// Native scrolling does the work (swipe, trackpad, arrow keys on the focused track); the buttons
// page by the visible width and grey out at either end.

const reducedMotion = (): boolean => matchMedia('(prefers-reduced-motion: reduce)').matches;

export function initCarousel(): void {
  const carousel = document.querySelector<HTMLElement>('.carousel');
  const track = carousel?.querySelector<HTMLElement>('.cards');
  const prev = carousel?.querySelector<HTMLButtonElement>('.prev');
  const next = carousel?.querySelector<HTMLButtonElement>('.next');
  if (!carousel || !track || !prev || !next) return;

  let frame = 0;
  const update = (): void => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      // Filters hide the track when nothing matches; the empty message then stands alone.
      carousel.hidden = track.hidden;
      const max = track.scrollWidth - track.clientWidth;
      const fits = max <= 1;
      carousel.classList.toggle('fits', fits);
      prev.disabled = fits || track.scrollLeft <= 1;
      next.disabled = fits || track.scrollLeft >= max - 1;
    });
  };

  const page = (direction: 1 | -1): void => {
    track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: reducedMotion() ? 'auto' : 'smooth' });
  };
  prev.addEventListener('click', () => page(-1));
  next.addEventListener('click', () => page(1));
  track.addEventListener('scroll', update, { passive: true });
  new ResizeObserver(update).observe(track);
  document.addEventListener('filters:applied', () => {
    track.scrollLeft = 0;
    update();
  });
  update();
}
