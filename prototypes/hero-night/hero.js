// The hero video: starts only when motion and data allow it, pauses off-screen, and has a
// pause button. This becomes src/scripts/hero.ts once the prototype is approved.
// Prototype-only query params: ?video=<path> overrides the clip, ?savedata forces the Save-Data path.

const KEY = 'hero-video-paused';

function allowed() {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  if (new URLSearchParams(location.search).has('savedata')) return false;
  const c = navigator.connection;
  if (c && (c.saveData || /(^|-)2g$|^3g$/.test(c.effectiveType ?? ''))) return false;
  return true;
}

function readPaused() {
  try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
}
function writePaused(v) {
  try { v ? localStorage.setItem(KEY, '1') : localStorage.removeItem(KEY); } catch {}
}

export function initHero() {
  const video = document.querySelector('[data-hero-video]');
  const button = document.querySelector('[data-hero-pause]');
  if (!video || !button || !allowed()) return;

  const phone = matchMedia('(max-width: 640px)').matches;
  const override = new URLSearchParams(location.search).get('video');
  const d = video.dataset;
  const srcs = override ? [override] : phone ? [d.phoneWebm, d.phoneMp4] : [d.webm, d.mp4];
  for (const src of srcs.filter(Boolean)) {
    const s = document.createElement('source');
    s.src = src;
    s.type = src.endsWith('.webm') ? 'video/webm' : 'video/mp4';
    video.append(s);
  }
  if (!video.querySelector('source')) return;

  let userPaused = readPaused();
  let visible = true;
  const show = () => { video.classList.add('on'); button.hidden = false; };
  const sync = () => {
    button.setAttribute('aria-pressed', String(userPaused));
    button.setAttribute('aria-label', userPaused ? 'Play background video' : 'Pause background video');
    if (userPaused || !visible || document.hidden) video.pause();
    else video.play().catch(() => {});
  };

  video.addEventListener('playing', show, { once: true });
  // Paused by choice on a previous visit: show the first frame and offer play.
  if (userPaused) video.addEventListener('loadeddata', show, { once: true });
  video.addEventListener('error', () => video.remove(), true);
  button.addEventListener('click', () => { userPaused = !userPaused; writePaused(userPaused); sync(); });
  document.addEventListener('visibilitychange', sync);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; sync(); }).observe(video);

  video.load();
  sync();
}
