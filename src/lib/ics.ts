// "Add to calendar" files (RFC 5545). Self-contained so `node --test` can run it directly.
// Gig times are Europe/London wall-clock times; the file carries them in UTC so every calendar
// app shows the right local time, including across the October and March clock changes.

export interface CalendarEvent {
  uid: string;
  title: string;
  /** YYYY-MM-DD, Europe/London */
  date: string;
  /** YYYY-MM-DD for events spanning several days */
  endDate?: string;
  /** HH:MM, Europe/London. Without it the event is all-day. */
  time?: string;
  durationHours?: number;
  location?: string;
  description?: string;
  url?: string;
  cancelled?: boolean;
  stamp: Date;
}

const TZ = 'Europe/London';

/** Minutes London is ahead of UTC at the given instant (0 in winter, 60 in summer). */
function londonOffsetMinutes(at: Date): number {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
      .formatToParts(at)
      .map((p) => [p.type, p.value]),
  );
  const asUtc = Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute);
  return Math.round((asUtc - at.getTime()) / 60_000);
}

/** The UTC instant of a Europe/London wall-clock time. */
export function londonToUtc(date: string, time: string): Date {
  const [y, m, d] = date.split('-').map(Number);
  const [hh, mm] = time.split(':').map(Number);
  const naive = Date.UTC(y, m - 1, d, hh, mm);
  let utc = naive - londonOffsetMinutes(new Date(naive)) * 60_000;
  utc = naive - londonOffsetMinutes(new Date(utc)) * 60_000; // settle near a clock change
  return new Date(utc);
}

const stampUtc = (d: Date) => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
const dateOnly = (date: string) => date.replace(/-/g, '');

function nextDay(date: string): string {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

export function escapeText(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');
}

/** Lines longer than 75 octets continue on the next line, which starts with a space. */
export function fold(line: string): string {
  const bytes = new TextEncoder();
  const out: string[] = [];
  let current = '';
  let size = 0;
  for (const ch of line) {
    const n = bytes.encode(ch).length;
    if (size + n > (out.length ? 74 : 75)) {
      out.push(current);
      current = '';
      size = 0;
    }
    current += ch;
    size += n;
  }
  out.push(current);
  return out.join('\r\n ');
}

export function toIcs(e: CalendarEvent): string {
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Belfast Gigs//Listings//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'BEGIN:VEVENT'];
  lines.push(`UID:${e.uid}`, `DTSTAMP:${stampUtc(e.stamp)}`);
  if (e.time) {
    const start = londonToUtc(e.date, e.time);
    const end = new Date(start.getTime() + (e.durationHours ?? 3) * 3_600_000);
    lines.push(`DTSTART:${stampUtc(start)}`, `DTEND:${stampUtc(end)}`);
  } else {
    lines.push(`DTSTART;VALUE=DATE:${dateOnly(e.date)}`, `DTEND;VALUE=DATE:${dateOnly(nextDay(e.endDate ?? e.date))}`);
  }
  lines.push(`SUMMARY:${escapeText(e.title)}`);
  if (e.location) lines.push(`LOCATION:${escapeText(e.location)}`);
  if (e.description) lines.push(`DESCRIPTION:${escapeText(e.description)}`);
  if (e.url) lines.push(`URL:${e.url}`);
  lines.push(`STATUS:${e.cancelled ? 'CANCELLED' : 'CONFIRMED'}`, 'END:VEVENT', 'END:VCALENDAR');
  return lines.map(fold).join('\r\n') + '\r\n';
}
