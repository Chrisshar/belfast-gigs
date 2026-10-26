"""End-to-end behaviour of applying scraped gigs to the content folder across several runs."""

from __future__ import annotations

from datetime import timedelta

from conftest import NOW, raw

from belfast_gigs import frontmatter
from belfast_gigs.pipeline.classify import classify
from belfast_gigs.pipeline.merge import Scored, cluster
from belfast_gigs.pipeline.normalise import prepare
from belfast_gigs.pipeline.write import MAX_DELETIONS, REMOVE_AFTER_MISSES, REVIEW_AFTER_MISSES, apply, load_gigs
from belfast_gigs.state import State
from belfast_gigs.venues import VenueIndex


class Runner:
    """Runs apply() the way __main__ does, against a temp site, keeping state between runs."""

    def __init__(self, site):
        self.site = site
        self.state = State.load(site["data"])
        self.venues = VenueIndex.load(site["venues"])
        self.now = NOW

    def run(self, *raws, healthy=("venue", "ticketmaster"), first_run=False, authority=None):
        scored = []
        for r in raws:
            p = prepare(r, self.venues, create_stubs=True, write_stubs=True)
            scored.append(Scored(p, classify(p), (authority or {}).get(r.source, 1 if r.source == "venue" else 5), first_run))
        changes = apply(cluster(scored), self.state, self.venues, self.site["gigs"], now=self.now, healthy_adapters=set(healthy), dry_run=False)
        self.now += timedelta(hours=12)
        return changes

    def gigs(self):
        return {g.path.stem: g.data for g in load_gigs(self.site["gigs"]).values()}

    def only(self):
        [(slug, data)] = self.gigs().items()
        return slug, data

    def edit(self, slug, **changes):
        path = self.site["gigs"] / f"{slug}.md"
        data, body = frontmatter.read(path)
        data.update(changes)
        frontmatter.write(path, data, body)


def test_new_gig_is_created_with_first_seen(site):
    r = Runner(site)
    changes = r.run(raw(title="Example Act - SOLD OUT", start_time="20:00"))
    slug, data = r.only()
    assert changes.created == [slug] and slug == "2026-11-14-ulster-hall-example-act"
    assert data["first_seen"] == "2026-10-25T17:00:00Z" and data["status"] == "sold_out"
    assert data["sources"] == [{"name": "venue", "key": "venue:1"}]
    assert "backfill" not in data


def test_rerun_with_same_data_changes_nothing(site):
    r = Runner(site)
    r.run(raw())
    before = r.only()
    changes = r.run(raw())
    assert changes.updated == [] and changes.unchanged == 1
    assert r.only() == before  # updated_at untouched, so no commit and no rebuild


def test_venue_and_ticketmaster_listings_merge_into_one_gig(site):
    r = Runner(site)
    r.run(
        raw(source="venue", source_key="venue:1", title="ASH", doors_time="19:00", tickets=[("Box office", "https://example.com/a")]),
        raw(source="ticketmaster", source_key="ticketmaster:9", title="Ash + special guests", start_time="20:00", price_min=25.0, tickets=[("Ticketmaster", "https://tm.example/a")]),
    )
    _, data = r.only()
    assert data["title"] == "ASH"  # the venue's own listing wins
    assert data["doors_time"] == "19:00" and data["start_time"] == "20:00" and data["price_min"] == 25
    assert [t["source"] for t in data["tickets"]] == ["Box office", "Ticketmaster"]
    assert {s["key"] for s in data["sources"]} == {"venue:1", "ticketmaster:9"}


def test_rescheduled_gig_keeps_its_file_id_and_first_seen(site):
    r = Runner(site)
    r.run(raw(date="2026-11-14"))
    slug, original = r.only()
    r.run(raw(date="2026-12-05", status="rescheduled"))
    new_slug, data = r.only()
    assert new_slug == slug and data["id"] == original["id"] and data["first_seen"] == original["first_seen"]
    assert data["date"] == "2026-12-05" and data["status"] == "rescheduled"


def test_human_edit_is_locked_and_kept(site):
    r = Runner(site)
    r.run(raw(start_time="20:00"))
    slug, _ = r.only()
    r.edit(slug, start_time="20:30", headliner="Example Act (acoustic)")
    changes = r.run(raw(start_time="20:00"))
    _, data = r.only()
    assert data["start_time"] == "20:30" and data["headliner"] == "Example Act (acoustic)"
    assert set(data["locked_fields"]) == {"start_time", "headliner"}
    assert len(changes.newly_locked) == 2
    r.run(raw(start_time="21:00"))  # later source changes don't override the lock
    assert r.only()[1]["start_time"] == "20:30"


def test_formatting_only_changes_are_not_edits(site):
    r = Runner(site)
    r.run(raw(price_min=18.0))
    slug, _ = r.only()
    path = site["gigs"] / f"{slug}.md"
    # What a CMS save might do: unquote the date, write 18.0, reorder nothing else.
    path.write_text(path.read_text(encoding="utf-8").replace('date: "2026-11-14"', "date: 2026-11-14").replace("price_min: 18", "price_min: 18.0"), encoding="utf-8")
    r.run(raw(price_min=18.0))
    assert "locked_fields" not in r.only()[1]


def test_cms_formatted_file_is_left_byte_for_byte(site):
    r = Runner(site)
    r.run(raw())
    slug, data = r.only()
    path = site["gigs"] / f"{slug}.md"
    # What a Sveltia save looks like: its own key order and list indentation, explicit defaults.
    lines = ["---"]
    for k, v in reversed(list(data.items())):
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                if isinstance(item, dict):
                    first, *rest = item.items()
                    lines.append(f'  - {first[0]}: "{first[1]}"')
                    lines.extend(f'    {ik}: "{iv}"' for ik, iv in rest)
                else:
                    lines.append(f'  - "{item}"')
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            lines.extend(f"  {ik}: {str(iv).lower() if isinstance(iv, bool) else iv}" for ik, iv in v.items())
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f'{k}: "{v}"')
    lines += ["free: false", "needs_review: false", 'currency: "GBP"', "---", ""]
    cms_text = "\n".join(lines)
    path.write_text(cms_text, encoding="utf-8", newline="\n")
    assert frontmatter.read(path)[0]["title"] == data["title"]
    changes = r.run(raw())
    assert changes.updated == [] and changes.newly_locked == []
    assert path.read_text(encoding="utf-8") == cms_text  # no formatting-only commit after a CMS save


def test_human_deleted_gig_is_never_re_added(site):
    r = Runner(site)
    r.run(raw())
    slug, _ = r.only()
    (site["gigs"] / f"{slug}.md").unlink()
    changes = r.run(raw())
    assert r.gigs() == {} and changes.suppressed and len(changes.human_deleted) == 1
    r.run(raw(title="Example Act (new support added)"))  # same source key: still suppressed
    assert r.gigs() == {}


def test_mass_disappearance_trips_the_safety_valve(site):
    r = Runner(site)
    raws = [raw(source_key=f"venue:{i}", title=f"Act Number {chr(65 + i)}{chr(65 + i)}", date=f"2026-11-{10 + i}") for i in range(MAX_DELETIONS + 1)]
    r.run(*raws)
    for path in site["gigs"].glob("*.md"):
        path.unlink()
    changes = r.run()
    assert changes.deletion_valve_tripped and r.state.tombstones == []


def test_hand_added_gig_only_has_gaps_filled(site):
    r = Runner(site)
    frontmatter.write(
        site["gigs"] / "2026-11-14-ulster-hall-example-act.md",
        {"id": "11111111-1111-4111-8111-111111111111", "title": "Example Act", "headliner": "Example Act", "venue": "ulster-hall", "date": "2026-11-14", "start_time": "19:30", "first_seen": "2026-10-01T09:00:00Z"},
    )
    for _ in range(2):  # the second run must still treat it as hand-added
        r.run(raw(start_time="20:00", price_min=20.0, tickets=[("Ticketmaster", "https://tm.example/x")]))
    _, data = r.only()
    assert data["start_time"] == "19:30"  # kept
    assert data["price_min"] == 20 and data["tickets"][0]["url"] == "https://tm.example/x"  # filled
    assert data["first_seen"] == "2026-10-01T09:00:00Z"


def test_gig_missing_from_healthy_sources_is_flagged_then_removed(site):
    r = Runner(site)
    r.run(raw())
    for _ in range(REVIEW_AFTER_MISSES):
        changes = r.run(raw(source_key="venue:other", title="Another Act Entirely", date="2026-11-20"))
    assert changes.flagged_missing and r.gigs()["2026-11-14-ulster-hall-example-act"]["needs_review"] is True
    for _ in range(REMOVE_AFTER_MISSES - REVIEW_AFTER_MISSES):
        changes = r.run(raw(source_key="venue:other", title="Another Act Entirely", date="2026-11-20"))
    assert changes.vanished == ["2026-11-14-ulster-hall-example-act"]
    # If it comes back, it's restored with its original first_seen, not shown as new.
    r.run(raw(), raw(source_key="venue:other", title="Another Act Entirely", date="2026-11-20"))
    assert r.gigs()["2026-11-14-ulster-hall-example-act"]["first_seen"] == "2026-10-25T17:00:00Z"


def test_missing_gig_is_not_counted_when_its_source_failed(site):
    r = Runner(site)
    r.run(raw())
    for _ in range(REMOVE_AFTER_MISSES + 1):
        r.run(healthy=())
    assert "2026-11-14-ulster-hall-example-act" in r.gigs()


def test_past_gigs_are_pruned(site):
    r = Runner(site)
    r.run(raw(date="2026-10-26"))
    r.now = NOW + timedelta(days=2)
    changes = r.run()
    assert changes.pruned == ["2026-10-26-ulster-hall-example-act"] and r.gigs() == {}
    assert r.state.snapshots == {}


def test_backfill_flag_only_on_first_run(site):
    r = Runner(site)
    r.run(raw(), first_run=True)
    assert r.only()[1]["backfill"] is True
    r.run(raw(source_key="venue:2", title="Brand New Act", date="2026-12-01"))
    assert "backfill" not in r.gigs()["2026-12-01-ulster-hall-brand-new-act"]


def test_unknown_belfast_venue_gets_a_stub(site):
    r = Runner(site)
    r.run(raw(venue_name="Some New Bar", address="1 Example Street, Belfast, BT1 1AA"))
    slug, data = r.only()
    assert data["venue"] == "some-new-bar"
    stub, _ = frontmatter.read(site["venues"] / "some-new-bar.md")
    assert stub["needs_review"] is True


def test_cleared_review_flag_stays_cleared(site):
    r = Runner(site)
    r.run(raw(title="Example Act", is_music_hint=None, venue_name="Black Box"))  # no signal: flagged
    slug, data = r.only()
    assert data["needs_review"] is True
    r.edit(slug, needs_review=False)
    r.run(raw(title="Example Act", is_music_hint=None, venue_name="Black Box"))
    _, data = r.only()
    assert data.get("needs_review") in (None, False) and "needs_review" in data["locked_fields"]
