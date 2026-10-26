import { getCollection, getEntry, type CollectionEntry } from 'astro:content';
import { daysBetween, londonToday, monthKey } from './dates';

export type Gig = CollectionEntry<'gigs'>;
export type Venue = CollectionEntry<'venues'>;

/** A gig with its venue resolved, ready for the listing pages. */
export interface GigView {
  gig: Gig;
  slug: string;
  venue: Venue | undefined;
  venueName: string;
  area: string;
  /** Lower-cased act, support and venue names for the search box. */
  search: string;
}

const RECENT_DAYS = 14;
const RECENT_MAX = 40;

function byDateThenTime(a: Gig, b: Gig): number {
  return (
    a.data.date.localeCompare(b.data.date) ||
    (a.data.start_time ?? a.data.doors_time ?? '').localeCompare(b.data.start_time ?? b.data.doors_time ?? '') ||
    a.data.headliner.localeCompare(b.data.headliner)
  );
}

/** Gigs from today onwards (Belfast time), in date order. */
export async function getUpcomingGigs(now: Date = new Date()): Promise<Gig[]> {
  const today = londonToday(now);
  const gigs = await getCollection('gigs', ({ data }) => (data.end_date ?? data.date) >= today);
  return gigs.sort(byDateThenTime);
}

export async function toViews(gigs: Gig[]): Promise<GigView[]> {
  return Promise.all(
    gigs.map(async (gig) => {
      const venue = await getEntry(gig.data.venue);
      const venueName = venue?.data.name ?? gig.data.venue.id;
      return {
        gig,
        slug: gig.id,
        venue,
        venueName,
        area: venue?.data.area ?? 'Belfast',
        search: [gig.data.headliner, gig.data.title, ...gig.data.support, venueName].join(' ').toLowerCase(),
      };
    }),
  );
}

/**
 * Newest announcements first. Backfilled gigs (found on a source's first-ever run, so
 * possibly announced months ago) never count as recently added.
 */
export function recentlyAdded<T extends { gig: Gig }>(views: T[], now: Date = new Date()): T[] {
  return views
    .filter(({ gig: { data } }) => !data.backfill && daysBetween(data.first_seen, now) <= RECENT_DAYS)
    .sort((a, b) => b.gig.data.first_seen.localeCompare(a.gig.data.first_seen) || byDateThenTime(a.gig, b.gig))
    .slice(0, RECENT_MAX);
}

/** month key -> day (YYYY-MM-DD) -> gigs, preserving order. */
export function groupByMonthAndDay<T extends { gig: Gig }>(views: T[]): Map<string, Map<string, T[]>> {
  const months = new Map<string, Map<string, T[]>>();
  for (const v of views) {
    const m = monthKey(v.gig.data.date);
    if (!months.has(m)) months.set(m, new Map());
    const days = months.get(m)!;
    if (!days.has(v.gig.data.date)) days.set(v.gig.data.date, []);
    days.get(v.gig.data.date)!.push(v);
  }
  return months;
}

export const STATUS_LABELS: Record<Gig['data']['status'], string> = {
  on_sale: 'On sale',
  sold_out: 'Sold out',
  cancelled: 'Cancelled',
  postponed: 'Postponed',
  rescheduled: 'Rescheduled',
};

export function formatPrice({ free, price_min, price_max }: Gig['data']): string | undefined {
  if (free) return 'Free';
  if (price_min === undefined) return undefined;
  const fmt = (n: number) => `£${Number.isInteger(n) ? n : n.toFixed(2)}`;
  return price_max !== undefined && price_max !== price_min ? `${fmt(price_min)}–${fmt(price_max)}` : fmt(price_min);
}

/** The data-* attributes the filter script reads. */
export function filterAttrs(v: GigView): Record<string, string> {
  const d = v.gig.data;
  return {
    'data-gig': '',
    'data-date': d.date,
    'data-end': d.end_date ?? d.date,
    'data-venue': d.venue.id,
    'data-month': monthKey(d.date),
    'data-genres': d.genres.join('|'),
    'data-area': v.area,
    'data-search': v.search,
  };
}
