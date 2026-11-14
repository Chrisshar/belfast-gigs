// The hero film (src/components/Hero.astro). It only plays when the visitor allows motion and
// isn't saving data; otherwise the poster still stays. It pauses while off-screen or in a hidden
// tab, and the pause button's choice is remembered in this browser.

import { motionAllowed } from './motion';

const KEY = 'hero-video-paused';

interface NetworkInformation { saveData?: boolean; effectiveType?: string }

function filmAllowed(): boolean {
  if (!motionAllowed()) return false;
  const c = (navigator as Navigator & { connection?: NetworkInformation }).connection;
  return !(c && (c.saveData || /(^|-)2g$|^3g$/.test(c.effectiveType ?? '')));
}

function readPaused(): boolean {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

function writePaused(paused: boolean): void {
  try {
    if (paused) localStorage.setItem(KEY, '1');
    else localStorage.removeItem(KEY);
  } catch {}
}

export function initHero(): void {
  const video = document.querySelector<HTMLVideoElement>('[data-hero-video]');
  const button = document.querySelector<HTMLButtonElement>('[data-hero-pause]');
  if (!video || !button || !filmAllowed()) return;

  // The 4:5 crop on phones, matching the poster the <picture> picks at the same width.
  const d = video.dataset;
  const phone = matchMedia('(max-width: 640px)').matches;
  for (const src of phone ? [d.phoneWebm, d.phoneMp4] : [d.webm, d.mp4]) {
    if (!src) continue;
    const source = document.createElement('source');
    source.src = src;
    source.type = src.endsWith('.webm') ? 'video/webm' : 'video/mp4';
    video.append(source);
  }

  let userPaused = readPaused();
  let visible = true;
  const show = (): void => {
    video.classList.add('on');
    button.hidden = false;
  };
  const sync = (): void => {
    button.setAttribute('aria-pressed', String(userPaused));
    button.setAttribute('aria-label', userPaused ? 'Play background video' : 'Pause background video');
    if (userPaused || !visible || document.hidden) video.pause();
    else video.play().catch(() => {});
  };

  video.addEventListener('playing', show, { once: true });
  // Paused by choice on an earlier visit: show the first frame and offer play.
  if (userPaused) video.addEventListener('loadeddata', show, { once: true });
  // Neither format plays: the poster stays and the button never appears.
  video.addEventListener('error', () => video.remove(), true);
  button.addEventListener('click', () => {
    userPaused = !userPaused;
    writePaused(userPaused);
    sync();
  });
  document.addEventListener('visibilitychange', sync);
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    sync();
  }).observe(video);

  video.load();
  sync();
}
