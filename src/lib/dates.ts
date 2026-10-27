// All gig dates and times are Europe/London local strings ("YYYY-MM-DD", "HH:MM").
export const TZ = 'Europe/London';

/** Today's date in Belfast as YYYY-MM-DD, regardless of where the code runs. */
export function londonToday(now: Date = new Date()): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}

// A local date string is a calendar day, not an instant. Anchoring it at UTC noon and
// formatting in UTC keeps the weekday and day number right in every timezone.
function asCalendarDay(date: string): Date {
  return new Date(`${date}T12:00:00Z`);
}

export function formatDate(date: string, opts: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }): string {
  return new Intl.DateTimeFormat('en-GB', { ...opts, timeZone: 'UTC' }).format(asCalendarDay(date));
}

export function dayParts(date: string) {
  const d = asCalendarDay(date);
  const f = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-GB', { ...o, timeZone: 'UTC' }).format(d);
  const year = d.getUTCFullYear();
  // " 2027" for a date outside the current year, so "Sat 9 Jan" isn't read as this January.
  const otherYear = String(year) === londonToday().slice(0, 4) ? '' : ` ${year}`;
  return { day: d.getUTCDate(), dow: f({ weekday: 'short' }), dowLong: f({ weekday: 'long' }), mon: f({ month: 'short' }), monLong: f({ month: 'long' }), year, otherYear };
}

export function monthKey(date: string): string {
  return date.slice(0, 7);
}

export function formatMonth(key: string): string {
  return formatDate(`${key}-01`, { month: 'long', year: 'numeric' });
}

export function daysBetween(fromIso: string, to: Date): number {
  return (to.getTime() - new Date(fromIso).getTime()) / 86_400_000;
}
