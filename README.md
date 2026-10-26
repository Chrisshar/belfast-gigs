# Belfast Gigs

Upcoming live music in Belfast and greater Belfast. A static [Astro](https://astro.build) site on Cloudflare, fed by a Python scraper that runs twice a day on GitHub Actions. Every gig is a Markdown file in `src/content/gigs/`.

> Status: **Phase 4**. The scraper runs twice a day on GitHub Actions (`.github/workflows/scrape.yml`) with Claude Haiku checking new listings, from the sources listed at the bottom. Gigs can be edited at `/admin` once the CMS login is set up. `PLAN-PROMPT.md` is the original brief.

## Automation

- **Scrape** (`.github/workflows/scrape.yml`): runs at 06:17 and 17:17 UTC, or by hand under **Actions → Scrape → Run workflow** (tick *Dry run* to see the report without changing anything).
  - Each run builds the site before pushing, so bad data never reaches Cloudflare.
  - If a CMS edit lands mid-run, it re-applies the run on top of the edit.
  - It opens GitHub issues when something needs you: **Source broken: …**, **Review queue**, **Scrape produced invalid data**.
  - The run report appears on each run's summary page.
- **CI** (`.github/workflows/ci.yml`): tests and builds every human push and pull request, including CMS commits.
- **Coverage check reminder** (`.github/workflows/benchmark-reminder.yml`): every Monday at 08:23 UTC, opens a **Weekly coverage check** issue (or comments on the open one).
- **Claude Haiku** checks each listing once, and the result is cached in `data/classify_cache.json`:
  - It decides whether the listing is a gig, cleans up the headliner and support acts, and picks genres.
  - Listings the source already marks as non-music (club nights, comedy) are never sent.
  - Limits: 150 calls per run and $5 per month, tracked in `data/llm_usage.json`. Past either limit, the rules decide alone, and anything uncertain is flagged for review.
- **Repository secrets:** `ANTHROPIC_API_KEY` (needed for Claude) and `TICKETMASTER_KEY` (optional). `CF_DEPLOY_HOOK` is only needed if Cloudflare stops building from the scraper's pushes.

## Layout

| Path | What's there |
|---|---|
| `src/content/gigs/` | One `.md` per gig. Written by the scraper and the CMS. |
| `src/content/venues/` | Hand-curated venues: name, aliases the scraper matches on, group, address. |
| `src/content/residencies/` | Weekly regular nights (open mics, trad sessions). |
| `src/content.config.ts` | Schemas for all three. Keep the genre and status lists in sync with the scraper. |
| `src/pages/` | Home (Recently added + Upcoming), gig detail pages, Regular nights, 404. |
| `scraper/` | Python scraper (`belfast_gigs` package, tests in `scraper/tests`). |
| `data/` | Scraper state (see below). Not part of the site build. |

## Local development (Windows)

```powershell
npm.cmd install
npm.cmd run dev      # http://localhost:4321
npm.cmd run build    # static output in dist/
npm.cmd run check    # type-check .astro and .ts files
```

All dates and times in gig files are **Europe/London local time**, written as quoted strings (`date: "2026-11-06"`, `start_time: "20:00"`).

## Scraper (Python 3.12+)

```powershell
python -m venv scraper/.venv
scraper/.venv/Scripts/python.exe -m pip install -e "./scraper[dev]"
scraper/.venv/Scripts/python.exe -m belfast_gigs run --dry-run       # fetch and report, write nothing
scraper/.venv/Scripts/python.exe -m belfast_gigs run                 # update src/content/gigs and data/
scraper/.venv/Scripts/python.exe -m belfast_gigs run --only limelight
scraper/.venv/Scripts/python.exe -m pytest scraper/tests
```

For local Ticketmaster runs, set the key for the current PowerShell session: `$env:TICKETMASTER_KEY = "..."`. Without it, that source is skipped.

How it treats your edits:
- **Edit a gig** (in the CMS or by hand): the scraper locks every field you changed (`locked_fields`) and never overwrites it.
- **Delete a future gig**: it's tombstoned in `data/tombstones.json` and never re-added.
- **Add a gig by hand**: the scraper only fills in fields you left empty.
- **Gigs from a source's first run** are marked `backfill: true` and stay out of "Recently added", because they weren't necessarily announced recently.
- **Block a listing for good**: add a title pattern to `data/overrides.yaml`.

## Weekly coverage check

Songkick and Eventbrite are never scraped, but they're a useful yardstick.
1. Once a week (GitHub opens an issue on Mondays as a reminder), open Songkick's Belfast concerts pages in your own browser and save them with **Ctrl+S** into `benchmark/inbox/`. That folder is gitignored.
2. In a Claude Code session in this repo, say **"run the coverage check"**. Claude follows `.claude/skills/coverage-check/SKILL.md`: it runs the command below, then reports what's missing, grouped by venue, with a suggestion for each (a new adapter, a venue alias, or a one-off gig to add in the CMS).

```powershell
scraper/.venv/Scripts/python.exe -m belfast_gigs benchmark benchmark/inbox
```

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

### 4. CMS login
The CMS lives at `/admin` (`public/admin/`). It signs in with GitHub through a small Cloudflare Worker.
1. Open https://deploy.workers.cloudflare.com/?url=https://github.com/sveltia/sveltia-cms-auth and deploy it to your Cloudflare account. Note the Worker's URL (e.g. `https://sveltia-cms-auth.<your-subdomain>.workers.dev`).
2. On GitHub: **Settings → Developer settings → OAuth Apps → New OAuth App**.
   - Homepage URL: the site's URL.
   - Authorization callback URL: `<worker URL>/callback`.
   - Generate a client secret.
3. In Cloudflare, on the Worker, under **Settings → Variables and Secrets**, add:
   - `GITHUB_CLIENT_ID`: the OAuth app's client ID.
   - `GITHUB_CLIENT_SECRET`: the client secret (type **Secret**).
   - `ALLOWED_DOMAINS`: `belfast-gigs.christopher-sharvin.workers.dev` (plus your own domain later).
4. If the Worker's URL differs from `base_url` in `public/admin/config.yml`, change it there.
5. Visit `/admin`, sign in with GitHub, and edit away. If a save is rejected because the scraper pushed in the meantime, reload and try again.

## Sources and licences

| Source | Adapter | How it's read |
|---|---|---|
| Limelight (and Shine shows at the Telegraph Building, Ormeau Park, Custom House Square) | `limelight` | Public venuecloud JSON API |
| The O2 Belfast | `o2belfast` | The site's public events JSON |
| Ulster Hall, Waterfront Hall | `ulsterhall` | Paged what's-on listing |
| The Belfast Empire Music Hall | `empire` | Listing plus each gig's page |
| Ulster Sports Club | `usc` | The calendar widget's public JSON |
| Voodoo | `voodoo` | Sitemap plus the 30 most recently edited event pages |
| Mandela Hall, The Union Bar (QUB SU) | `mandela` | The Glistrr box office page's embedded event data |
| Black Box | `blackbox` | Paged event listing, by category |
| Oh Yeah Music Centre | `ohyeah` | Events page HTML |
| The Duncairn | `duncairn` | `/live-music` plus each event's page |
| The Deer's Head | `deershead` | Music Hall listing |
| Moving On Music (promoter) | `movingon` | WordPress REST API plus each show's page |
| The Harrison Chambers of Distinction | `harrison` | Music listing |
| Citizen Ticket organisers (American Bar and others) | `citizenticket` | Organiser pages |
| Ticketmaster | `ticketmaster` | Discovery API (needs `TICKETMASTER_KEY`) |

Sunflower has no listings of its own; its weekly nights are in `src/content/residencies/`.

Ticketmaster's Discovery API terms bar earning money from the API outside its affiliate programme. Venue sites are read politely: robots.txt respected, an identifying user agent, and at least 2 seconds between requests. Songkick, Eventbrite and Skiddle are **not** scraped. Songkick and Eventbrite pages you save yourself are used only for the weekly coverage check.
