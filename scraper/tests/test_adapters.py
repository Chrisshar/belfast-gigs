from conftest import load_json, load_text

from belfast_gigs.adapters import citizenticket, harrison, limelight, o2belfast, ticketmaster


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
