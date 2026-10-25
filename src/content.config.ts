import { defineCollection, reference } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// Keep these lists in sync with scraper/belfast_gigs/models.py.
export const GENRES = [
  'Rock',
  'Indie/Alternative',
  'Punk/Hardcore',
  'Metal',
  'Pop',
  'Hip-Hop/Rap',
  'Electronic',
  'Folk/Trad',
  'Country/Americana',
  'Jazz/Blues',
  'Soul/R&B/Funk',
  'Singer-Songwriter',
  'Tribute/Covers',
  'World',
  'Contemporary/New Music',
] as const;

export const STATUSES = ['on_sale', 'sold_out', 'cancelled', 'postponed', 'rescheduled'] as const;

export const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const;

// Dates and times stay as strings in Europe/London local time. YAML would otherwise turn
// unquoted dates into UTC-midnight Date objects, which can shift a gig by a day.
const localDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Expected YYYY-MM-DD');
const localTime = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Expected HH:MM (24h)');
const isoTimestamp = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/, 'Expected ISO 8601 timestamp');

const venues = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/venues' }),
  schema: z.object({
    name: z.string(),
    // Other spellings sources use for this venue; the scraper matches against name + aliases.
    aliases: z.array(z.string()).default([]),
    // Venues sharing a building or operator (e.g. QUB SU rooms) share a group so dedupe compares them.
    group: z.string().optional(),
    rooms: z.array(z.string()).default([]),
    area: z.string().default('Belfast'),
    address: z.string().optional(),
    postcode: z.string().optional(),
    lat: z.number().optional(),
    lng: z.number().optional(),
    website: z.url().optional(),
    music_only: z.boolean().default(false),
    needs_review: z.boolean().default(false),
  }),
});

const gigs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/gigs' }),
  schema: z.object({
    id: z.uuid(),
    title: z.string(),
    headliner: z.string(),
    support: z.array(z.string()).default([]),
    venue: reference('venues'),
    room: z.string().optional(),
    date: localDate,
    end_date: localDate.optional(),
    doors_time: localTime.optional(),
    start_time: localTime.optional(),
    price_min: z.number().nonnegative().optional(),
    price_max: z.number().nonnegative().optional(),
    currency: z.literal('GBP').default('GBP'),
    free: z.boolean().default(false),
    status: z.enum(STATUSES).default('on_sale'),
    age_restriction: z.string().optional(),
    genres: z.array(z.enum(GENRES)).default([]),
    tickets: z
      .array(z.object({ source: z.string(), url: z.url() }))
      .default([]),
    sources: z
      .array(z.object({ name: z.string(), key: z.string(), url: z.url().optional() }))
      .default([]),
    first_seen: isoTimestamp,
    updated_at: isoTimestamp.optional(),
    backfill: z.boolean().default(false),
    classification: z
      .object({
        is_music: z.boolean(),
        confidence: z.number().min(0).max(1),
        method: z.enum(['rules', 'llm', 'manual']),
      })
      .optional(),
    needs_review: z.boolean().default(false),
    locked_fields: z.array(z.string()).default([]),
  }),
});

const residencies = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/residencies' }),
  schema: z.object({
    venue: reference('venues'),
    nights: z.array(
      z.object({
        weekday: z.enum(WEEKDAYS),
        title: z.string(),
        start_time: localTime.optional(),
        genres: z.array(z.enum(GENRES)).default([]),
        free: z.boolean().optional(),
        notes: z.string().optional(),
      }),
    ),
    needs_review: z.boolean().default(false),
  }),
});

export const collections = { venues, gigs, residencies };
