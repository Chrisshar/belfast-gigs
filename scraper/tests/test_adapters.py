from datetime import date

from conftest import load_json, load_text

from belfast_gigs.adapters import (
    blackbox,
    citizenticket,
    deershead,
    duncairn,
    empire,
    harrison,
    limelight,
    mandela,
    movingon,
    o2belfast,
    ohyeah,
    ticketmaster,
    ulsterhall,
    usc,
    voodoo,
    wix,
)
from belfast_gigs.http import HttpError
from belfast_gigs.models import RawEvent


class TestLimelight:
    events = limelight.parse(load_json("limelight", "events.json"))

    def test_parses_every_listing(self):
        assert len(self.events) == 331

    def test_gig_fields(self):
        ev = next(e for e in self.events if e.title == "St. Paul & The Broken Bones")
        assert ev.source_key == "limelight:10764"
        assert ev.venue_name == "Limelight 1" and ev.room == "Limelight 1"
        assert ev.date == "2026-10-25" and ev.doors_time == "19:00" and ev.start_time is None
        assert ev.support == ["Melina Malone"]
        assert ev.age_restriction == "18+"
        assert ev.tickets[0][0] == "Ticketmaster"
        assert ev.is_music_hint is True

    def test_club_nights_are_marked_non_music(self):
        club = [e for e in self.events if e.venue_name == "Limelight"]
        assert club and all(e.is_music_hint is False for e in club)
        shine = [e for e in self.events if any("shine.tickets" in url for _, url in e.tickets)]
        assert all(e.is_music_hint is False for e in shine)

    def test_comedy_is_marked_non_music(self):
        comedy = [e for e in self.events if "comedy" in e.categories]
        assert len(comedy) == 21 and all(e.is_music_hint is False for e in comedy)

    def test_tagline_subtitles_are_not_support_acts(self):
        huey = next(e for e in self.events if e.title == "Huey Morgan")
        assert huey.support == []


class TestO2Belfast:
    listing = next(e for e in load_json("o2belfast", "events-page1.json")["data"] if e["id"] == 260525)

    def test_one_event_per_night_with_doors_and_ticket(self):
        nights = o2belfast.parse_event(self.listing, load_text("o2belfast", "detail-westlife.html"))
        dates = [n.date for n in nights]
        assert dates[0] == "2026-10-27" and dates[-1] == "2026-11-06"
        assert len(set(dates)) == len(dates)
        assert all(n.doors_time == "18:30" for n in nights)
        assert all(n.tickets and "ticketmaster" in n.tickets[0][1] for n in nights)
        assert not any("suite" in url for n in nights for _, url in n.tickets)
        assert nights[0].support == ["Ana Sky"]
        assert {n.source_key for n in nights} == {f"o2belfast:260525:{d}" for d in dates}

    def test_falls_back_to_listing_dates_without_detail(self):
        [ev] = o2belfast.parse_event(self.listing, "")
        assert ev.date == "2026-10-27" and ev.end_date == "2026-11-06"


class TestHarrison:
    items = harrison.parse_listing(load_text("harrison", "music.html"))

    def item(self, path):
        return next(i for i in self.items if i["path"] == path)

    def test_listing(self):
        assert len(self.items) == 44 and len({i["path"] for i in self.items}) == 44
        assert self.items[0]["title"] == "Angeline Ball" and self.items[0]["ends_ms"] == 1793226600654

    def test_event_uses_local_clock_time_and_ticket_link(self):
        ev = harrison.parse_event(self.item("/unified-calendar/liney-hamilton-trio"), load_text("harrison", "liney-hamilton-trio.html"))
        assert ev.title == "Linley Hamilton Trio" and ev.date == "2026-11-02" and ev.start_time == "20:00"
        assert ev.tickets == [("TicketSource", "https://www.ticketsource.com/monday-club-events/linley-hamilton-trio/e-ljkvjr")]
        assert ev.venue_name == "The Harrison Chambers of Distinction" and ev.source_key == "harrison:liney-hamilton-trio"

    def test_late_finish_is_not_a_second_day(self):
        ev = harrison.parse_event(self.item("/unified-calendar/mckowski-dj-night-sound-of-belfast-2026"), load_text("harrison", "mckowski-dj-night.html"))
        assert ev.date == "2026-11-11" and ev.start_time == "22:00" and ev.end_date is None

    def test_blue_room_series_prefix_is_not_the_headliner(self):
        item = {"path": "/unified-calendar/x", "title": "Blue Room Sessions: Joe Krown", "excerpt": "", "ends_ms": None}
        ev = harrison.parse_event(item, load_text("harrison", "liney-hamilton-trio.html"))
        assert ev.headliner == "Joe Krown" and ev.room == "Blue Room"


class TestCitizenTicket:
    def test_sitemap_keeps_only_chosen_organisers(self):
        urls = citizenticket.event_urls(load_text("citizenticket", "sitemap.xml"))
        assert urls and all("/events/dock-street-jazz-club/" in u for u in urls)

    def test_event_page(self):
        url = "https://www.citizenticket.com/events/dock-street-jazz-club/dock-street-jazz-jam/"
        ev = citizenticket.parse_event(url, load_text("citizenticket", "dock-street-jazz-jam.html"))
        assert (ev.title, ev.date, ev.start_time, ev.price_min) == ("Dock Street Jazz Jam", "2026-11-01", "20:30", 8.0)
        assert ev.venue_name == "The American Bar" and ev.address.endswith("BT15 1LF")
        assert ev.source_key == "citizenticket:dock-street-jazz-club/dock-street-jazz-jam"

    def test_finished_event_redirects_to_organiser_page_and_is_skipped(self):
        url = "https://www.citizenticket.com/events/dock-street-jazz-club/dock-street-jazz-club-john-stowell-us/"
        assert citizenticket.parse_event(url, load_text("citizenticket", "dock-street-jazz-club-john-stowell-us.html")) is None

    def test_time_range_with_a_decoded_hyphen(self):
        html = load_text("citizenticket", "dock-street-jazz-jam.html").replace("&hyphen;", "‐")
        ev = citizenticket.parse_event("https://www.citizenticket.com/events/dock-street-jazz-club/dock-street-jazz-jam/", html)
        assert ev is not None and ev.start_time == "20:30"

    def test_headliner_drops_club_prefix_and_country(self):
        html = load_text("citizenticket", "dock-street-jazz-jam.html").replace("<title>Dock Street Jazz Jam", "<title>Dock Street Jazz Club: Kirk MacDonald (CA)")
        ev = citizenticket.parse_event("https://www.citizenticket.com/events/dock-street-jazz-club/x/", html)
        assert ev.headliner == "Kirk MacDonald"


class TestTicketmaster:
    events = ticketmaster.collapse(ticketmaster.parse(load_json("ticketmaster", "events-synthetic.json")))

    def test_drops_packages_and_parking_and_collapses_duplicates(self):
        names = [e.title for e in self.events]
        assert names.count("Example Rock Band") == 1
        assert not any("VIP" in n or "Parking" in n or "Seated" in n for n in names)

    def test_collapsed_listing_keeps_both_ticket_links(self):
        rock = next(e for e in self.events if e.title == "Example Rock Band")
        assert len(rock.tickets) == 2

    def test_fields(self):
        rock = next(e for e in self.events if e.title == "Example Rock Band")
        assert rock.headliner == "Example Rock Band" and rock.support == ["Sample Support"]
        assert rock.start_time == "19:00" and rock.price_min == 25 and rock.price_max == 32.5
        assert rock.categories == ["rock", "alternative rock"]

    def test_tba_time_cancelled_and_non_gbp_price(self):
        folk = next(e for e in self.events if e.title == "Example Folk Singer")
        assert folk.start_time is None  # never derived from the UTC dateTime
        assert folk.status == "cancelled"
        assert folk.price_min is None  # EUR prices are ignored

    def test_missing_key_is_skipped_not_failed(self, monkeypatch):
        monkeypatch.delenv("TICKETMASTER_KEY", raising=False)
        try:
            ticketmaster.Ticketmaster().fetch(None)  # type: ignore[arg-type]
        except ticketmaster.MissingCredentials:
            pass
        else:
            raise AssertionError("expected MissingCredentials")


class TestUlsterHall:
    events = ulsterhall.parse_page(load_text("ulsterhall", "page1.html"))

    def test_both_halls_and_rooms(self):
        assert len(self.events) == 12
        kj = next(e for e in self.events if e.title == "Katherine Jenkins")
        assert (kj.venue_name, kj.room, kj.date, kj.status) == ("Waterfront Hall", "Main Auditorium", "2026-10-27", "sold_out")
        gurriers = next(e for e in self.events if e.title == "Gurriers")
        assert gurriers.venue_name == "Ulster Hall" and gurriers.room is None and gurriers.status == "on_sale"

    def test_genre_class_sets_the_music_hint(self):
        hints = {e.title: e.is_music_hint for e in self.events}
        assert hints["Proud Mary"] is True
        assert hints["Gary Meikle: Yer Maw"] is False and hints["The Addams Family"] is False
        assert hints["Richard Ayoade"] is False


class TestEmpire:
    events = empire.parse_listing(load_text("empire", "music-hall.html"))

    def test_listing(self):
        assert len(self.events) == 24
        ev = self.events[0]
        assert (ev.title, ev.date, ev.start_time) == ("Panchiko", "2026-10-30", "19:00")
        assert ev.source_key == "empire:panchiko"
        assert any(e.title == "The Stranger - A Tribute to Billy Joel" for e in self.events)

    def test_detail_adds_price_and_ticketmaster(self):
        ev = empire.with_detail(empire.parse_listing(load_text("empire", "music-hall.html"))[0], load_text("empire", "detail.html"))
        assert ev.price_min == 31.75
        assert ev.tickets and ev.tickets[0][0] == "Ticketmaster"


class TestUlsterSportsClub:
    events = usc.parse(load_json("usc", "calendar.json"), "2026-10-26")

    def test_only_future_events(self):
        assert len(self.events) == 17 and all(e.date >= "2026-10-26" for e in self.events)

    def test_fields(self):
        ev = next(e for e in self.events if e.title == "Discharge")
        assert (ev.date, ev.start_time, ev.venue_name) == ("2027-03-05", "19:00", "Ulster Sports Club")
        assert ev.tickets[0][0] == "Eventbrite" and ev.is_music_hint is None


class TestVoodoo:
    def test_most_recently_edited_pages_first(self):
        entries = wix.sitemap_entries(load_text("voodoo", "events-sitemap.xml"))
        assert len(entries) > 600 and all("/events/" in u for u, _ in entries)
        assert entries[0] == ("https://www.voodoobelfast.com/events/emo-club", "2026-10-22")

    def test_event_page(self):
        ev = voodoo.parse_event("https://www.voodoobelfast.com/events/emo-club", load_text("voodoo", "event1.html"))
        assert ev and (ev.title, ev.date, ev.start_time, ev.price_min) == ("Emo Club", "2026-10-30", "22:00", 10.0)
        assert ev.source_key == "voodoo:emo-club" and ev.tickets[0][0] == "Skiddle"


class TestMandelaHall:
    events = mandela.parse(load_text("mandela", "glistrr.html"))

    def test_reads_the_embedded_events(self):
        assert len(self.events) == 12
        ev = next(e for e in self.events if e.title == "Bell X1")
        assert (ev.date, ev.start_time, ev.venue_name, ev.price_min) == ("2026-12-12", "19:00", "Mandela Hall", 35.0)
        assert ev.age_restriction == "18+" and ev.is_music_hint is True and ev.tickets[0][0] == "Glistrr"

    def test_sold_out_comedy_and_club_nights(self):
        duke = next(e for e in self.events if e.title.startswith("Duke Special"))
        assert duke.status == "sold_out" and duke.price_min is None
        riot = next(e for e in self.events if "Club night" in e.title)
        assert riot.venue_name == "The Union Bar" and riot.is_music_hint is False
        assert all(e.is_music_hint is False for e in self.events if "comedy" in e.categories)


class TestBlackBox:
    events = {e.source_key: e for e in blackbox.parse_page(load_text("blackbox", "live-music.html"))}

    def test_featured_strip_is_deduplicated(self):
        assert len(blackbox.parse_page(load_text("blackbox", "live-music.html"))) == 27 and len(self.events) == 24

    def test_categories_and_fields(self):
        andy = next(e for e in self.events.values() if e.title == "Andy Irvine & Quilty")
        assert (andy.date, andy.start_time, andy.price_min, andy.is_music_hint) == ("2026-11-04", "19:30", 25.0, True)
        slip = next(e for e in self.events.values() if e.title == "The First Slip")
        assert slip.room == "Green Room" and slip.free
        open_mic = next(e for e in self.events.values() if e.title == "Black Box Open Mic")
        assert open_mic.is_music_hint is None  # left to the rules, which know open mics count
        assert all(e.is_music_hint is False for e in self.events.values() if "comedy" in e.categories)


class TestOhYeah:
    events = ohyeah.parse(load_text("ohyeah", "events.html"))

    def test_upcoming_only(self):
        assert len(self.events) == 58

    def test_fields(self):
        ev = next(e for e in self.events if e.title.startswith("Classic Album Night: Snow Patrol"))
        assert (ev.date, ev.start_time, ev.venue_name, ev.is_music_hint) == ("2026-11-06", "19:30", "Oh Yeah Music Centre", True)

    def test_late_finish_is_not_multi_day(self):
        ev = next(e for e in self.events if "New Éire" in e.title)
        assert ev.date == "2026-11-07" and ev.end_date is None

    def test_mixed_and_off_site_events(self):
        tour = next(e for e in self.events if e.title.startswith("Belfast Music Walking Tour"))
        assert tour.venue_name == "Ulster Hall" and tour.is_music_hint is None
        assert next(e for e in self.events if e.title.startswith("PULSE#2")).is_music_hint is False


class TestDeersHead:
    events = deershead.parse(load_text("deershead", "music-hall.html"), "2026-10-26")

    def test_listing_with_inferred_years(self):
        assert len(self.events) == 22
        glaspy = self.events[0]
        assert (glaspy.title, glaspy.date, glaspy.start_time, glaspy.price_min) == ("Margaret Glaspy", "2026-10-28", "19:30", 15.0)
        assert glaspy.tickets[0][0] == "Eventbrite"
        assert next(e for e in self.events if e.title == "Ariel Posen").date == "2027-02-10"


class TestDuncairn:
    events = duncairn.parse_listing(load_text("duncairn", "live-music.html"))

    def test_listing(self):
        assert len(self.events) == 9
        assert self.events[0].date == "2026-11-07" and self.events[0].source_url.endswith("/events/friel-sisters")

    def test_detail_adds_time_tickets_and_age(self):
        ev = duncairn.with_detail(next(e for e in self.events if e.title == "John Spillane"), load_text("duncairn", "detail.html"))
        assert ev.start_time == "19:00" and ev.age_restriction == "18+"
        assert ev.tickets == [("Ticketsolve", "https://theduncairn.ticketsolve.com/ticketbooth/shows/1173650591")]


class TestMovingOnMusic:
    def parse(self, slug):
        return movingon.parse_page(f"https://www.movingonmusic.com/whats-on/{slug}/", load_text("movingon", f"{slug}.html"), "2026-10-26")

    def test_promoter_line(self):
        ev = self.parse("arborist-looking-for-love-album-launch")
        assert (ev.date, ev.start_time, ev.venue_name, ev.price_min) == ("2026-11-19", "19:30", "The Empire", 17.5)
        assert ev.tickets[0][0] == "Citizen Ticket" and ev.is_music_hint is True

    def test_room_and_venue(self):
        ev = self.parse("chamber-choir-ireland")
        assert (ev.venue_name, ev.room, ev.price_min, ev.price_max) == ("Titanic Hotel", "Drawing Office One", 10.0, 15.0)
        assert "Belfast" in (ev.address or "")

    def test_venue_site_event_page(self):
        ev = mandela.parse_wix_event("https://www.mandelahall.com/events/corto.alto", load_text("mandela", "wix-event.html"))
        assert ev and (ev.title, ev.date, ev.start_time, ev.price_min) == ("corto.alto", "2026-11-05", "19:00", 22.0)
        assert ev.status == "on_sale"  # "SOLD OUT" is in every page's template
        assert ev.venue_name == "Mandela Hall" and ev.is_music_hint is None


class FakeWixSite:
    """A Wix site: url -> (lastmod, event date). Counts the event pages read."""

    def __init__(self, pages: dict[str, tuple[str, str]]):
        self.pages, self.reads = pages, []

    def get_text(self, url: str) -> str:
        if url.endswith("/sitemap.xml"):
            return "<loc>https://x.test/dynamic-events-sitemap.xml</loc>"
        if "dynamic-events" in url:
            return "".join(f"<url><loc>{u}</loc><lastmod>{m}</lastmod></url>" for u, (m, _) in self.pages.items())
        self.reads.append(url)
        return self.pages[url][1]


def page_event(url: str, html: str) -> RawEvent:
    return RawEvent(source="t", source_key=url, title=url.rsplit("/", 1)[-1], venue_name="V", date=html, tickets=[("T", url)])


class TestWixPageCache:
    today = date(2026, 10, 26)

    def site(self) -> FakeWixSite:
        return FakeWixSite({
            "https://x.test/events/new": ("2026-10-25", "2026-12-01"),
            "https://x.test/events/old-but-upcoming": ("2026-08-26", "2027-01-10"),
            "https://x.test/events/older-but-upcoming": ("2026-06-01", "2027-02-01"),
            "https://x.test/events/past": ("2026-05-01", "2026-05-20"),
            "https://x.test/events/ancient": ("2024-01-01", "2024-02-01"),
        })

    def test_every_upcoming_page_is_read_once_then_remembered(self, monkeypatch):
        monkeypatch.setattr(wix, "MAX_FETCH", 2)
        site, cache = self.site(), {}
        first = wix.events(site, "https://x.test", cache, page_event, self.today)
        assert [e.title for e in first] == ["new", "old-but-upcoming"]
        second = wix.events(site, "https://x.test", cache, page_event, self.today)
        assert sorted(e.title for e in second) == ["new", "old-but-upcoming", "older-but-upcoming"]
        reads = len(site.reads)
        third = wix.events(site, "https://x.test", cache, page_event, self.today)
        assert len(third) == 3 and len(site.reads) == reads == 4  # the year-old page is never read
        assert third[0].tickets == [("T", "https://x.test/events/new")]
        assert cache["https://x.test/events/past"]["event"] is None

    def test_edited_page_is_read_again(self):
        site, cache = self.site(), {}
        wix.events(site, "https://x.test", cache, page_event, self.today)
        site.pages["https://x.test/events/new"] = ("2026-10-26", "2026-12-02")
        events = wix.events(site, "https://x.test", cache, page_event, self.today)
        assert site.reads[-1] == "https://x.test/events/new"
        assert next(e for e in events if e.title == "new").date == "2026-12-02"

    def test_old_pages_found_late_are_backfill(self):
        events = wix.events(self.site(), "https://x.test", {}, page_event, self.today)
        assert {e.title: e.backfill for e in events} == {"new": False, "old-but-upcoming": True, "older-but-upcoming": True}

    def test_escaped_urls_and_missing_pages(self):
        site = self.site()
        site.pages["https://x.test/events/we&apos;re-gone"] = ("2026-10-20", "2026-12-24")
        real_get = site.get_text

        def get_text(url):
            if url.endswith("we're-gone"):
                site.reads.append(url)
                raise HttpError(url, 404)
            return real_get(url)

        site.get_text = get_text
        cache = {}
        events = wix.events(site, "https://x.test", cache, page_event, self.today)
        assert len(events) == 3 and cache["https://x.test/events/we're-gone"]["event"] is None
