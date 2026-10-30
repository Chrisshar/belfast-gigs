// Run with: node --test src/lib/links.test.ts   (Node 22.18+ strips the types itself)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { venueEventUrl } from './links.ts';

test("a page on the venue's own site is used, with or without www.", () => {
  const page = 'https://thebelfastempire.com/music-hall/panchiko/';
  assert.equal(venueEventUrl([{ url: page }], 'https://www.thebelfastempire.com/music-hall/'), page);
  assert.equal(venueEventUrl([{ url: 'https://www.voodoobelfast.com/events/x' }], 'https://voodoobelfast.com/'), 'https://www.voodoobelfast.com/events/x');
});

test('a homepage, a ticket seller or a missing url is not a gig page', () => {
  assert.equal(venueEventUrl([{ url: 'https://www.limelightbelfast.com/' }], 'https://www.limelightbelfast.com/'), undefined);
  assert.equal(venueEventUrl([{ url: 'https://www.glistrr.com/events/e/x' }], 'https://www.mandelahall.com/'), undefined);
  assert.equal(venueEventUrl([{}], 'https://www.ulstersportsclub.com/'), undefined);
});

test('a venue without a website gets no link', () => {
  assert.equal(venueEventUrl([{ url: 'https://www.crescentarts.org/events/x' }], undefined), undefined);
});

test("the venue's own page wins over other sources", () => {
  const sources = [{ url: 'https://www.glistrr.com/events/e/x' }, { url: 'https://www.ticketmaster.ie/event/1' }, { url: 'https://www.mandelahall.com/events/x' }];
  assert.equal(venueEventUrl(sources, 'https://www.mandelahall.com/'), 'https://www.mandelahall.com/events/x');
});
