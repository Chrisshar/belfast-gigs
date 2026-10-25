// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Placeholder until the site has a name and domain. Override with SITE_URL in the build environment.
const site = process.env.SITE_URL ?? 'https://belfast-gigs.christopher-sharvin.workers.dev';

export default defineConfig({
  site,
  output: 'static',
  integrations: [sitemap()],
});
