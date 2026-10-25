# Belfast Gigs

Upcoming live music in Belfast and greater Belfast. A static [Astro](https://astro.build) site on Cloudflare, fed by a Python scraper that runs twice a day on GitHub Actions. Every gig is a Markdown file in `src/content/gigs/`.

> Status: **Phase 0** (site skeleton with sample data). The scraper arrives in Phase 1. The full plan lives outside the repo; `PLAN-PROMPT.md` is the original brief.

## Layout

| Path | What's there |
|---|---|
| `src/content/gigs/` | One `.md` per gig. Written by the scraper and the CMS. |
| `src/content/venues/` | Hand-curated venues: name, aliases the scraper matches on, group, address. |
| `src/content/residencies/` | Weekly regular nights (open mics, trad sessions). |
| `src/content.config.ts` | Schemas for all three. Keep the genre and status lists in sync with the scraper. |
| `src/pages/` | Home (Recently added + Upcoming), gig detail pages, Regular nights, 404. |
| `scraper/` | *(Phase 1)* Python scraper. |
| `data/` | *(Phase 1)* Scraper state: overrides, tombstones, caches. Not part of the site build. |

## Local development (Windows)

```powershell
npm.cmd install
npm.cmd run dev      # http://localhost:4321
npm.cmd run build    # static output in dist/
npm.cmd run check    # type-check .astro and .ts files
```

All dates and times in gig files are **Europe/London local time**, written as quoted strings (`date: "2026-11-06"`, `start_time: "20:00"`).

## One-time setup (only you can do these)

### 1. GitHub repo
1. On github.com, create a **public** repository (placeholder name `belfast-gigs`). Public repos get unlimited Actions minutes.
2. In this folder:
   ```powershell
   git remote add origin https://github.com/<you>/belfast-gigs.git
   git push -u origin main
   ```

### 2. Cloudflare (Workers static assets)
1. Sign up at dash.cloudflare.com (free plan).
2. **Workers & Pages → Create → Import a repository**, connect GitHub, and pick `belfast-gigs`.
3. Build settings:
   - Build command: `npm run build`
   - Deploy command: `npx wrangler deploy`
4. **Settings → Build → Build watch paths:**
   - Include: `src/*`, `public/*`, `astro.config.*`, `package*.json`, `wrangler.jsonc`
   - Exclude: `scraper/*`, `data/*`, `.github/*`
5. The site appears at `https://belfast-gigs.<your-subdomain>.workers.dev`. When you have a domain, set `SITE_URL` as a build variable.

### 3. API keys *(needed from Phase 1/2)*
- **Ticketmaster:** register at developer.ticketmaster.com and copy the Consumer Key.
- **Anthropic:** in console.anthropic.com, create a workspace with a **$5/month** spend limit, then create an API key inside it.
- In GitHub, under **Settings → Secrets and variables → Actions**, add `TICKETMASTER_KEY` and `ANTHROPIC_API_KEY`.

### 4. CMS login *(Phase 4)*
1. Deploy [sveltia-cms-auth](https://github.com/sveltia/sveltia-cms-auth) to Cloudflare.
2. Create a GitHub OAuth app with callback `https://<auth-worker>/callback`.
3. Set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` and `ALLOWED_DOMAINS` on the auth Worker.

## Sources and licences

Ticketmaster's Discovery API terms bar earning money from the API outside its affiliate programme. Venue sites are read politely: robots.txt respected, an identifying user agent, and at least 2 seconds between requests. Songkick, Eventbrite and Skiddle are **not** scraped. Songkick and Eventbrite pages you save yourself are used only for the weekly coverage check.
