// Client-side filtering over the server-rendered listing. Every gig element carries data-*
// attributes (see filterAttrs in src/lib/gigs.ts). State lives in the URL query string, so a
// filtered view can be bookmarked and shared:
//   ?when=weekend&venue=limelight&month=2026-11&genre=Rock&genre=Metal&area=Belfast&q=ash
// Genres combine with OR; the other filters combine with AND.

type When = '' | 'tonight' | 'weekend' | 'week';

interface State {
  when: When;
  q: string;
  venue: string;
  month: string;
  area: string;
  genres: Set<string>;
}

const TZ = 'Europe/London';

/** Today in Belfast as YYYY-MM-DD, wherever the visitor is. */
function londonToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

function addDays(date: string, n: number): string {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function weekday(date: string): number {
  return new Date(`${date}T12:00:00Z`).getUTCDay(); // 0 = Sunday
}

/** [from, to] inclusive for the quick filters. "This weekend" is Friday to Sunday; on a weekend day it starts today. */
function range(when: When, today: string): [string, string] | null {
  if (when === 'tonight') return [today, today];
  if (when === 'week') return [today, addDays(today, 6)];
  if (when === 'weekend') {
    const dow = weekday(today);
    if (dow === 0) return [today, today];
    const friday = dow >= 5 ? today : addDays(today, 5 - dow);
    return [friday, addDays(today, 7 - dow)];
  }
  return null;
}

function readUrl(): State {
  const p = new URLSearchParams(location.search);
  const when = p.get('when');
  return {
    when: when === 'tonight' || when === 'weekend' || when === 'week' ? when : '',
    q: p.get('q') ?? '',
    venue: p.get('venue') ?? '',
    month: p.get('month') ?? '',
    area: p.get('area') ?? '',
    genres: new Set(p.getAll('genre')),
  };
}

function writeUrl(s: State): void {
  const p = new URLSearchParams();
  if (s.when) p.set('when', s.when);
  if (s.q) p.set('q', s.q);
  if (s.venue) p.set('venue', s.venue);
  if (s.month) p.set('month', s.month);
  if (s.area) p.set('area', s.area);
  for (const g of s.genres) p.append('genre', g);
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}

function isFiltered(s: State): boolean {
  return Boolean(s.when || s.q || s.venue || s.month || s.area || s.genres.size);
}

function matches(el: HTMLElement, s: State, today: string): boolean {
  const { date = '', end = date, venue, month, area, genres = '', search = '' } = el.dataset;
  if (end < today) return false; // happened since the site was last built
  const r = range(s.when, today);
  if (r && (date > r[1] || end < r[0])) return false;
  if (s.venue && venue !== s.venue) return false;
  if (s.month && month !== s.month) return false;
  if (s.area && area !== s.area) return false;
  if (s.genres.size && !genres.split('|').some((g) => s.genres.has(g))) return false;
  if (s.q && !s.q.toLowerCase().split(/\s+/).every((word) => search.includes(word))) return false;
  return true;
}

const COMING_UP_MAX = 6;

/** Keep the hero current between builds: today's date, the seven-day count, the Coming up panel. */
function refreshHero(today: string): void {
  const dateLine = document.querySelector<HTMLElement>('[data-today]');
  if (dateLine) {
    dateLine.textContent = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'long', day: 'numeric', month: 'long' }).format(new Date()).replace(',', '');
  }
  const weekEnd = addDays(today, 6);
  const weekCount = document.querySelector<HTMLElement>('[data-week-count]');
  if (weekCount) {
    const gigs = document.querySelectorAll<HTMLElement>('[data-list=upcoming] [data-gig]');
    weekCount.textContent = String([...gigs].filter((el) => (el.dataset.end ?? '') >= today && (el.dataset.date ?? '') <= weekEnd).length);
  }
  // Nothing on tonight: don't lead with a button that opens an empty list.
  const tonight = document.querySelector<HTMLElement>('[data-jump=tonight]');
  if (tonight) {
    const any = [...document.querySelectorAll<HTMLElement>('[data-list=upcoming] [data-gig]')].some((el) => (el.dataset.date ?? '') <= today && (el.dataset.end ?? '') >= today);
    tonight.hidden = !any;
    document.querySelector('[data-jump=weekend]')?.classList.toggle('primary', !any);
  }
  let shown = 0;
  const runs = new Set<string>();
  for (const item of document.querySelectorAll<HTMLElement>('[data-coming] [data-end]')) {
    const run = item.dataset.run ?? '';
    item.hidden = (item.dataset.end ?? '') < today || shown >= COMING_UP_MAX || runs.has(run);
    if (!item.hidden) {
      shown++;
      runs.add(run);
    }
  }
  for (const day of document.querySelectorAll<HTMLElement>('[data-coming-day]')) {
    day.hidden = !day.querySelector('[data-end]:not([hidden])');
  }
  const panel = document.querySelector<HTMLElement>('[data-coming]');
  if (panel) panel.hidden = shown === 0;
}

export function initFilters(): void {
  const form = document.querySelector<HTMLFormElement>('#filters');
  if (!form) return;
  refreshHero(londonToday());
  const count = document.querySelector<HTMLElement>('#count');
  const state = readUrl();

  const whenButtons = [...form.querySelectorAll<HTMLButtonElement>('[data-when]')];
  const genreButtons = [...form.querySelectorAll<HTMLButtonElement>('[data-genre]')];
  const fields = {
    q: form.querySelector<HTMLInputElement>('[name=q]'),
    venue: form.querySelector<HTMLSelectElement>('[name=venue]'),
    month: form.querySelector<HTMLSelectElement>('[name=month]'),
    area: form.querySelector<HTMLSelectElement>('[name=area]'),
  };
  const clearButtons = [...document.querySelectorAll<HTMLButtonElement>('.clear')];
  const more = form.querySelector<HTMLButtonElement>('.more');

  function syncControls(): void {
    whenButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.when === state.when)));
    genreButtons.forEach((b) => b.setAttribute('aria-pressed', String(state.genres.has(b.dataset.genre ?? ''))));
    if (fields.q) fields.q.value = state.q;
    if (fields.venue) fields.venue.value = state.venue;
    if (fields.month) fields.month.value = state.month;
    if (fields.area) fields.area.value = state.area;
  }

  function apply(): void {
    const today = londonToday();
    let upcoming = 0;
    for (const list of document.querySelectorAll<HTMLElement>('[data-list]')) {
      let shown = 0;
      for (const el of list.querySelectorAll<HTMLElement>('[data-gig]')) {
        const ok = matches(el, state, today);
        el.hidden = !ok;
        if (ok) shown++;
      }
      // Hide day and month headings with nothing left under them.
      for (const group of list.querySelectorAll<HTMLElement>('[data-group=day], [data-group=month]')) {
        group.hidden = !group.querySelector('[data-gig]:not([hidden])');
      }
      const empty = document.querySelector<HTMLElement>(`[data-empty=${list.dataset.list}]`);
      if (empty) empty.hidden = shown > 0;
      list.hidden = shown === 0;
      if (list.dataset.list === 'upcoming') upcoming = shown;
    }
    const filtered = isFiltered(state);
    if (count) count.textContent = `${upcoming} ${upcoming === 1 ? 'gig' : 'gigs'}${filtered ? ' match' : ' coming up'}`;
    clearButtons.forEach((b) => (b.hidden = !filtered && !b.closest('[data-empty]')));
    writeUrl(state);
  }

  whenButtons.forEach((b) =>
    b.addEventListener('click', () => {
      state.when = state.when === b.dataset.when ? '' : ((b.dataset.when ?? '') as When);
      syncControls();
      apply();
    }),
  );
  genreButtons.forEach((b) =>
    b.addEventListener('click', () => {
      const g = b.dataset.genre ?? '';
      if (state.genres.has(g)) state.genres.delete(g);
      else state.genres.add(g);
      syncControls();
      apply();
    }),
  );
  fields.q?.addEventListener('input', () => {
    state.q = fields.q!.value.trim();
    apply();
  });
  for (const key of ['venue', 'month', 'area'] as const) {
    fields[key]?.addEventListener('change', () => {
      state[key] = fields[key]!.value;
      apply();
    });
  }
  clearButtons.forEach((b) =>
    b.addEventListener('click', () => {
      Object.assign(state, { when: '', q: '', venue: '', month: '', area: '', genres: new Set() });
      syncControls();
      apply();
    }),
  );
  // The hero's Tonight / This weekend / Next 7 days links set the same quick filter, then jump to
  // the list. Without JavaScript they still work, as plain ?when= links.
  for (const link of document.querySelectorAll<HTMLAnchorElement>('[data-jump]')) {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      state.when = (link.dataset.jump ?? '') as When;
      syncControls();
      apply();
      document.querySelector('#upcoming-h')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }
  more?.addEventListener('click', () => {
    const open = form.classList.toggle('open');
    more.setAttribute('aria-expanded', String(open));
  });
  // On phones the extra filters start folded; open them if the URL already uses one.
  if (state.q || state.venue || state.month || state.area || state.genres.size) {
    form.classList.add('open');
    more?.setAttribute('aria-expanded', 'true');
  }

  syncControls();
  apply();
}
