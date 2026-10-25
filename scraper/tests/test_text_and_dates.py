from datetime import UTC, datetime

import pytest

from belfast_gigs import frontmatter
from belfast_gigs.dates import london_today, parse_time, to_london
from belfast_gigs.pipeline.normalise import clean_title, is_pass, split_acts


@pytest.mark.parametrize(
    ("text", "expected"),
    [("7pm", "19:00"), ("7.30PM", "19:30"), ("Doors Open 6:30pm", "18:30"), ("19:45", "19:45"), ("12am", "00:00"), ("18+", None), ("", None)],
)
def test_parse_time(text, expected):
    assert parse_time(text) == expected


def test_clock_changes():
    # 25 Oct 2026: BST ends at 02:00 local. 1 Feb is GMT, 1 Jul is BST.
    assert to_london(datetime(2026, 10, 25, 0, 30, tzinfo=UTC)) == ("2026-10-25", "01:30")
    assert to_london(datetime(2026, 10, 25, 1, 30, tzinfo=UTC)) == ("2026-10-25", "01:30")
    assert to_london(datetime(2027, 3, 28, 1, 30, tzinfo=UTC)) == ("2027-03-28", "02:30")
    assert to_london(datetime(2027, 2, 1, 19, 0, tzinfo=UTC)) == ("2027-02-01", "19:00")
    assert to_london(datetime(2027, 7, 1, 19, 0, tzinfo=UTC)) == ("2027-07-01", "20:00")


def test_london_today_after_midnight_in_summer():
    # 23:30 UTC on 1 July is already 2 July in Belfast.
    assert london_today(datetime(2027, 7, 1, 23, 30, tzinfo=UTC)) == "2027-07-02"


@pytest.mark.parametrize(
    ("title", "clean", "status"),
    [
        ("Example Act - SOLD OUT", "Example Act", "sold_out"),
        ("Example Act (SOLD OUT)", "Example Act", "sold_out"),
        ("**CANCELLED** Example Act", "Example Act", "cancelled"),
        ("Example Act: NEW DATE", "Example Act", "rescheduled"),
        ("Example Act", "Example Act", None),
    ],
)
def test_clean_title(title, clean, status):
    assert clean_title(title) == (clean, status)


@pytest.mark.parametrize(
    ("title", "headliner", "support"),
    [
        ("An Evening With Ash + Pillow Queens", "Ash", ["Pillow Queens"]),
        ("Ash w/ special guests", "Ash", []),
        ("Example Band + Support", "Example Band", []),
        ("Westlife 25: The Anniversary World Tour - 25 Years Of Hits", "Westlife 25", []),
        ("Eerieland - Terror Talks", "Eerieland", []),
        ("Shine Presents: Example DJ", "Example DJ", []),
        ("Craic Sabbath & Ozzified - Halloween Special", "Craic Sabbath & Ozzified", []),
    ],
)
def test_split_acts(title, headliner, support):
    assert split_acts(title) == (headliner, support)


def test_clean_url_drops_tracking_but_keeps_real_params():
    from belfast_gigs.text import clean_url

    url = "https://secure.waterfront.co.uk/25852/25853?_ga=2.1.2&queueittoken=e_x~ts_1&utm_source=x"
    assert clean_url(url) == "https://secure.waterfront.co.uk/25852/25853"
    assert clean_url("https://tm.example/event/1?camefrom=CFC_X&brand=ie") == "https://tm.example/event/1?camefrom=CFC_X&brand=ie"


def test_frontmatter_handles_str_subclasses(tmp_path):
    class Fancy(str):
        pass

    path = tmp_path / "g.md"
    frontmatter.write(path, {"url": Fancy("https://example.com")}, "")
    assert 'url: "https://example.com"' in path.read_text(encoding="utf-8")


def test_passes_are_detected():
    assert is_pass("Belsonic Weekend Pass") and is_pass("Festival tickets: camping pass")
    assert not is_pass("Example Act")


def test_frontmatter_quotes_dates_and_times(tmp_path):
    path = tmp_path / "g.md"
    frontmatter.write(path, {"date": "2026-11-06", "start_time": "19:30", "price_min": 18.0, "price_max": 28.5, "free": False}, "")
    text = path.read_text(encoding="utf-8")
    assert 'date: "2026-11-06"' in text and 'start_time: "19:30"' in text
    assert "price_min: 18\n" in text and "price_max: 28.5\n" in text
    data, _ = frontmatter.read(path)
    assert data["date"] == "2026-11-06" and data["start_time"] == "19:30"
