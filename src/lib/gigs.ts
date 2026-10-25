import { getCollection, type CollectionEntry } from 'astro:content';
import { daysBetween, londonToday, monthKey } from './dates';

export type Gig = CollectionEntry<'gigs'>;

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

/**
 * Newest announcements first. Backfilled gigs (found on a source's first-ever run, so
 * possibly announced months ago) never count as recently added.
 */
export function recentlyAdded(gigs: Gig[], now: Date = new Date()): Gig[] {
  return gigs
    .filter(({ data }) => !data.backfill && daysBetween(data.first_seen, now) <= RECENT_DAYS)
    .sort((a, b) => b.data.first_seen.localeCompare(a.data.first_seen) || byDateThenTime(a, b))
    .slice(0, RECENT_MAX);
}

export function groupByMonth(gigs: Gig[]): Map<string, Gig[]> {
  const groups = new Map<string, Gig[]>();
  for (const gig of gigs) {
    const key = monthKey(gig.data.date);
    groups.set(key, [...(groups.get(key) ?? []), gig]);
  }
  return groups;
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
