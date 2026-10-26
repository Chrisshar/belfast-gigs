// Run with: node --test src/lib/ics.test.ts   (Node 22.18+ strips the types itself)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { escapeText, fold, londonToUtc, toIcs } from './ics.ts';

test('London wall-clock times convert to UTC across the clock changes', () => {
  assert.equal(londonToUtc('2026-11-06', '20:00').toISOString(), '2026-11-06T20:00:00.000Z'); // GMT
  assert.equal(londonToUtc('2027-07-01', '20:00').toISOString(), '2027-07-01T19:00:00.000Z'); // BST
  assert.equal(londonToUtc('2026-10-24', '19:30').toISOString(), '2026-10-24T18:30:00.000Z'); // day before BST ends
  assert.equal(londonToUtc('2026-10-25', '19:30').toISOString(), '2026-10-25T19:30:00.000Z'); // BST ended that morning
  assert.equal(londonToUtc('2027-03-28', '20:00').toISOString(), '2027-03-28T19:00:00.000Z'); // BST began that morning
});

test('text escaping and line folding follow RFC 5545', () => {
  assert.equal(escapeText('Ash, Pillow Queens; live\nin Belfast\\NI'), 'Ash\\, Pillow Queens\\; live\\nin Belfast\\\\NI');
  const folded = fold('DESCRIPTION:' + 'x'.repeat(200));
  for (const line of folded.split('\r\n')) assert.ok(new TextEncoder().encode(line).length <= 75);
  assert.equal(folded.replace(/\r\n /g, ''), 'DESCRIPTION:' + 'x'.repeat(200));
  // Multi-byte characters are never split.
  const accents = fold('SUMMARY:' + 'é'.repeat(60));
  assert.equal(accents.replace(/\r\n /g, ''), 'SUMMARY:' + 'é'.repeat(60));
});

test('timed, all-day and cancelled events', () => {
  const stamp = new Date('2026-10-26T12:00:00Z');
  const timed = toIcs({ uid: 'a@x', title: 'Ash', date: '2027-07-01', time: '20:00', location: 'Limelight, Belfast', stamp });
  assert.match(timed, /DTSTART:20270701T190000Z\r\nDTEND:20270701T220000Z/);
  assert.match(timed, /LOCATION:Limelight\\, Belfast/);
  assert.ok(timed.endsWith('END:VCALENDAR\r\n') && !/[^\r]\n/.test(timed));
  const allDay = toIcs({ uid: 'b@x', title: 'Belsonic', date: '2027-06-11', endDate: '2027-06-13', stamp });
  assert.match(allDay, /DTSTART;VALUE=DATE:20270611\r\nDTEND;VALUE=DATE:20270614/);
  assert.match(toIcs({ uid: 'c@x', title: 'Off', date: '2027-01-01', cancelled: true, stamp }), /STATUS:CANCELLED/);
});
