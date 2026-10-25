# Plan: Belfast gig listings site + twice-daily scraper

You're in plan mode. Plan how to build a static website that lists upcoming live music gigs in Belfast and greater Belfast, plus the scraper that keeps it up to date. Don't write production code yet. Read this whole brief, verify the assumptions marked **[verify]**, ask me about anything still ambiguous, then give me a phased plan to approve.

I'm on Windows 11 (PowerShell; run npm as `npm.cmd`). I have a GitHub account. There's no site name yet, so use a placeholder and the free `*.pages.dev` / `*.workers.dev` domain. The project folder is `C:\Design\Belfast Gig Listings` (empty, not a git repo yet).

---

## 1. Decisions already made

| Area | Decision |
|---|---|
| Site framework | **Astro** (static output) unless you find a strong reason not to. Content collections hold one Markdown file per gig. |
| Data store | **Markdown files with YAML frontmatter**, committed to git. No SQL database and no runtime backend. |
| Hosting | **Cloudflare free tier** (Pages, or Workers static assets, whichever Cloudflare currently recommends **[verify]**), deployed automatically on every push to `main`. |
| Scraper runtime | **GitHub Actions** cron, **twice a day**, running Python + **[Scrapling](https://github.com/D4Vinci/Scrapling)**. It commits changed `.md` files, and the push triggers the Cloudflare rebuild. |
| Smart filtering | **Rules + fuzzy matching first. Claude Haiku (`claude-haiku-5-5`) via the Anthropic API only for new or ambiguous events.** The API key is stored as a GitHub Actions secret. |
| Area | **Belfast + greater Belfast** (roughly Songkick's Belfast metro: the city plus places like Holywood, Lisburn and Newtownabbey). |
| Past gigs | **Delete** each gig's `.md` file once its date has passed. |
| Editing / fixes | **[Sveltia CMS](https://github.com/sveltia/sveltia-cms)** at `/admin`, editing the same Markdown files through GitHub. Its GitHub OAuth goes through a free Cloudflare Worker (e.g. `sveltia-cms-auth`) **[verify]**. |
| Visual design | **Bold gig-poster style**: high contrast, big expressive type, flyer/punk energy, dark by default. It still has to be readable, accessible (WCAG AA) and fast. |
| v1 extras | **A detail page for every gig** and an **"Add to calendar" `.ics`** download for each one. |

## 2. What the site does

### Pages
1. **Home / listings**
   - **Recently added**: the newest gigs **by when they were first discovered** (`first_seen`), newest first, covering roughly the last 14 days or the latest 30 or so, whichever you think reads better. This order must stay stable: re-scraping a gig must never reset its `first_seen`.
   - **Upcoming gigs**: every future gig in date order, grouped by day or month.
2. **Gig detail page** (`/gigs/<slug>/`): headliner, support acts, venue (with address and a map link), date, doors and start times, price where known, age restriction, status (on sale / sold out / cancelled / postponed / rescheduled), genres, every ticket link with its source (Ticketmaster, the venue's own site, etc.), and an **Add to calendar (.ics)** button generated at build time.
3. **/admin**: the Sveltia CMS.

### Filters (client-side, no server)
- **Venue** (multi-select)
- **Month**
- **Genre** (multi-select, from a fixed taxonomy; see §4)
- **Area** (Belfast city vs. Holywood / Lisburn / etc.)
- **Free-text search** (artist or venue)
- Quick chips: **Tonight**, **This weekend**, **Next 7 days**

Filter state should live in the URL query string so filtered views can be shared and bookmarked. Pick the lightest approach (vanilla JS over a build-time JSON index, a small island, or Pagefind) and say why.

### Non-functional
- Fast on mobile, with no heavy framework for the filtering.
- Basic SEO: schema.org `MusicEvent` JSON-LD on detail pages, a sitemap and Open Graph tags.
- Stays inside free tiers: Cloudflare build limits, GitHub Actions minutes and Anthropic spend (put a hard monthly budget guard on LLM calls).
- Images: decide whether to show any. Avoid hotlinking or rehosting copyrighted promo artwork unless a source clearly permits it. A typographic poster design without photos is fine.

## 3. Data model

Propose the exact schemas (Astro content collection with Zod, plus the matching Python model). At minimum:

**Gig (`src/content/gigs/<slug>.md`)**
- `id`: stable, deterministic ID (e.g. a hash of venue + date + normalised headliner)
- `title`, `headliner`, `support[]`
- `venue`: reference to a venue entry
- `date`, `doors_time`, `start_time` (Europe/London; handle BST/GMT correctly)
- `price_min`, `price_max`, `currency`, `free`
- `status`: on_sale | sold_out | cancelled | postponed | rescheduled
- `genres[]`: from the fixed taxonomy
- `age_restriction`
- `tickets[]`: `{ source, url }`, merged from every source that lists the gig
- `sources[]`: `{ name, url, first_seen, last_seen }`
- `first_seen`: drives "Recently added" and is never overwritten
- `updated_at`
- `classification`: `{ is_music, confidence, method: rules|llm|manual }`
- `locked_fields[]`: fields a human has edited in the CMS, which the scraper must never overwrite
- Body: an optional short description

**Venue (`src/content/venues/<slug>.md` or a YAML data collection)**
- name, **aliases[]** (e.g. "Mandela Hall", "QUB Students' Union – Mandela Hall"), address, area/town, lat/lng, website, capacity (optional)

**Scraper state (committed, outside the content folder)**
- A **blocklist/override file** (YAML) for events or patterns that must never be re-added (non-music events that slipped through, or a gig a human deleted).
- A **classification cache** keyed by an event fingerprint, so the same event is never sent to the LLM twice.
- An **index of recently deleted IDs** (past or manually removed), so a deleted gig isn't resurrected by a source that's slow to remove it.

## 4. Scraper requirements

### Sources (verify each one, see §5)
- **Aggregator:** Songkick Belfast metro: https://www.songkick.com/metro-areas/24523-uk-belfast
- **Venues and promoters:**
  - https://www.limelightbelfast.com/
  - https://www.mandelahall.com/
  - https://www.thebelfastempire.com/music-hall/
  - https://www.movingonmusic.com/
  - Suggest other major Belfast music venues and promoters worth adding (e.g. Ulster Hall / Waterfront, SSE Arena, Telegraph Building, Oh Yeah, Black Box, Voodoo, Ulster Sports Club, Sunflower, Aiken, Shine/Sound of Belfast). Propose a priority order; don't add them all blindly.
- **Ticketing:** Ticketmaster, Eventbrite, Citizen Ticket. Also assess Skiddle, Dice, See Tickets and TicketSource.

### Approach per source
- **Prefer official APIs and structured data over HTML scraping**, e.g. the Ticketmaster Discovery API (free key), any Skiddle/Eventbrite API that's still available, and `application/ld+json` `Event`/`MusicEvent` blocks on venue pages. Use Scrapling's plain `Fetcher` for static HTML, and its dynamic/browser fetcher only where JS rendering is genuinely needed.
- **Be a polite scraper:** respect `robots.txt` and each site's terms, set a descriptive User-Agent, rate-limit, and cache responses during a run. **Don't use anti-bot or CAPTCHA bypass.** If a source blocks automated access or forbids scraping in its ToS, flag it and propose an alternative (official API, feed, or drop it). Songkick in particular: check its ToS and API status **[verify]**.
- Each source is a **pluggable adapter** with a common interface (`fetch() -> list[RawEvent]`), so adding a venue means writing one small file.

### Pipeline (each run)
1. **Fetch** every enabled source. One source failing must not break the run.
2. **Normalise**: venue names via the alias table, dates/times to Europe/London, prices to GBP, headliner/support split, title clean-up ("+ support", "SOLD OUT", "(Tour 2027)", etc.).
3. **Geo filter**: drop venues outside greater Belfast.
4. **Music filter**: rules first (venue allowlists for music-only rooms; keyword blocklist for comedy, theatre, panto, quiz, club-night-only, talks, family shows, sport; source category fields). Send only what the rules can't settle to Claude Haiku with structured output (`is_music`, `confidence`, `genres`, `headliner`, `support`). Cache every result.
5. **Dedupe/merge**: match on venue + date + fuzzy headliner (e.g. `rapidfuzz`), so "ASH" and "Ash + special guests" at the Limelight on the same date are one gig. Merge ticket links and sources, and prefer the most authoritative source for each field (venue site > ticketing > aggregator). Send borderline matches to the LLM. Also catch the same gig listed with slightly different times or venue room names.
6. **Genre tagging** into a fixed top-level taxonomy (propose roughly 10–15, e.g. Rock, Indie, Punk/Hardcore, Metal, Pop, Hip-Hop/Rap, Electronic, Folk/Trad, Country/Americana, Jazz/Blues, Soul/R&B/Funk, Classical, Singer-Songwriter, Tribute/Covers). Free sources such as MusicBrainz or Last.fm tags first, LLM as fallback.
7. **Write**: create or update Markdown files. Never overwrite `first_seen` or anything in `locked_fields`. Update `last_seen`/status. Mark cancellations rather than silently deleting them.
8. **Prune**: delete files for gigs whose date has passed, and record their IDs.
9. **Commit and push** only if something changed, with a clear commit message (e.g. "scrape: +7 new, 3 updated, 12 removed").

### Scheduling and ops
- GitHub Actions cron twice a day (morning and early evening UK time; note that cron runs in UTC, so allow for BST). Also `workflow_dispatch` for manual runs.
- A `concurrency` guard so runs never overlap, and safe handling if I've edited via the CMS in the meantime (pull/rebase before commit).
- Cache pip and Playwright browsers between runs.
- **Health reporting:** a per-run summary (events per source, new/updated/removed, LLM calls and cost) shown in the Actions job summary. Auto-open or update a GitHub issue when a source returns zero events or errors on consecutive runs, since that usually means the site's layout changed.
- **Tests:** saved HTML/JSON fixtures per adapter with pytest parsing tests, unit tests for normalisation, dedupe and the music filter, and an Astro build check in CI.

## 5. What I want from you in plan mode

1. **Verify before planning**: fetch each listed source (read-only) and report for each: is there an API, JSON-LD or an RSS feed? Is the page static or JS-rendered? What do `robots.txt` and the ToS say? How hard is it to parse? Also confirm the current state of: Cloudflare Pages vs. Workers static assets for Astro, Scrapling's current API and fetcher names, Sveltia CMS auth on Cloudflare, and the Ticketmaster/Eventbrite/Skiddle API availability.
2. **Ask me questions** about anything that's still unclear before finalising.
3. **Propose the repo structure** (one repo with `site/` and `scraper/`, or root-level Astro with a `scraper/` folder, and why).
4. **Give a phased plan**, e.g.:
   - Phase 0: repo, Astro skeleton, Cloudflare deploy, schemas, seed venues
   - Phase 1: 2–3 high-value adapters plus the full pipeline (normalise → filter → dedupe → write → prune) running locally
   - Phase 2: GitHub Actions schedule, health reporting, LLM classification with budget guard
   - Phase 3: listings UI, filters, detail pages, `.ics`, poster-style design (show me 2–3 design directions within "bold gig poster" before committing)
   - Phase 4: Sveltia CMS + locked fields, remaining adapters, SEO polish
   Each phase should list deliverables, the files touched, and how I can check it works.
5. **List the setup steps only I can do** (create the GitHub repo, Cloudflare account/project, Anthropic API key and spend limit, Ticketmaster API key, GitHub OAuth app for Sveltia) with exact steps for each.
6. **Flag risks**: sources that may block scraping, ToS concerns, layout fragility, LLM cost, build-minute limits, timezone bugs, and anything else you notice.
