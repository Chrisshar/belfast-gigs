import type { APIRoute, GetStaticPaths } from 'astro';
import { getCollection } from 'astro:content';
import { toViews, type GigView } from '../../lib/gigs';
import { toIcs } from '../../lib/ics';

export const getStaticPaths = (async () => {
  const views = await toViews(await getCollection('gigs'));
  return views.map((view) => ({ params: { slug: view.slug }, props: { view } }));
}) satisfies GetStaticPaths;

export const GET = (({ props, site }) => {
  const { view } = props as { view: GigView };
  const d = view.gig.data;
  const page = new URL(`/gigs/${view.slug}/`, site).href;
  const venue = view.venue?.data;
  const location = [view.venueName, d.room, venue?.address, venue?.postcode].filter(Boolean).join(', ');
  const description = [d.support.length ? `With ${d.support.join(', ')}.` : '', d.doors_time ? `Doors ${d.doors_time}.` : '', page].filter(Boolean).join(' ');
  const ics = toIcs({
    uid: `${d.id}@belfast-gigs`,
    title: `${d.title} at ${view.venueName}`,
    date: d.date,
    endDate: d.end_date,
    time: d.start_time ?? d.doors_time,
    location,
    description,
    url: page,
    cancelled: d.status === 'cancelled',
    stamp: new Date(d.updated_at ?? d.first_seen),
  });
  return new Response(ics, { headers: { 'Content-Type': 'text/calendar; charset=utf-8' } });
}) satisfies APIRoute;
