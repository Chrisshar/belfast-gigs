import pytest
from conftest import raw

from belfast_gigs.pipeline.classify import classify
from belfast_gigs.pipeline.match import MATCH, Facts, name_score, score
from belfast_gigs.pipeline.normalise import prepare
from belfast_gigs.venues import VenueIndex


def facts(headliner, *, group="limelight", date="2026-11-06", room=None, time=None, end_date=None):
    return Facts(group, date, end_date, room, time, headliner)


class TestMatch:
    def test_same_act_with_support_wording_merges(self):
        assert score(facts("ASH"), facts("Ash + special guests")) >= MATCH

    def test_tour_name_variants_merge(self):
        assert score(facts("Westlife 25"), facts("Westlife")) >= MATCH

    def test_tribute_never_matches_the_real_act(self):
        assert score(facts("Oasis"), facts("Oasis tribute: Definitely Mightbe")) == 0

    def test_different_rooms_same_night_dont_merge(self):
        assert score(facts("Example", room="Limelight 1"), facts("Example", room="Limelight 2")) == 0

    def test_matinee_and_evening_dont_merge(self):
        assert score(facts("Example", time="14:00"), facts("Example", time="19:30")) == 0

    def test_subset_names_dont_falsely_merge(self):
        assert name_score("Ash", "Ash Tree Session") < MATCH

    def test_different_venue_groups_never_match(self):
        assert score(facts("Example"), facts("Example", group="ulster-hall")) == 0

    def test_multi_night_run_overlaps_single_night(self):
        assert score(facts("Westlife", date="2026-10-27", end_date="2026-11-06"), facts("Westlife", date="2026-10-30")) >= MATCH


@pytest.fixture(scope="module")
def venues():
    return VenueIndex.load()


@pytest.mark.parametrize(
    ("title", "venue", "hint", "is_music", "review"),
    [
        ("Kevin Example Live: Stand-Up Tour", "Ulster Hall", None, False, False),
        ("Example Queen Tribute", "Ulster Hall", None, True, False),
        ("Monday Open Mic", "Black Box", None, True, False),
        ("Pub Quiz", "Black Box", None, False, False),
        ("Example Act", "Black Box", None, True, True),  # no signal: publish, flag for review
        ("UFO", "Limelight", False, False, False),  # source says club night
        ("Example Band", "Limelight 2", True, True, False),
        ("Example Comedy Night", "Limelight 2", True, True, True),  # music source, comedy title
        ("Mystery Thing", "The Sunflower", None, True, False),  # music-only venue
        ("Ulster Orchestra: Example Symphony", "Ulster Hall", None, False, False),
        # Party nights go even when the source lists them as music.
        ("Black Parade Halloween Party", "Belfast Empire", True, False, False),
        ("Meltdown'S Halloween Headbangerz Ball", "Mandela Hall", True, False, False),
        ("NOUGHTIE NINETIES – 90’s – 00’s", "Belfast Empire", True, False, False),
        ("PLEASUREDOME 80’s / 90’s CHRISTMAS CRACKERS", "Belfast Empire", True, False, False),
        ("EMO FEST", "Limelight", True, False, False),
        ("STUDENT XMAS DAY 2026", "Limelight", True, False, False),
        ("Mystery Party", "The Sunflower", None, False, False),  # even at a music-only venue
        ("Tom Gee: EP Launch Party", "Crescent Arts Centre", True, True, False),
        ("Niall Horan: Dinner Party Live on Tour", "The O2 Belfast", True, True, False),
        ("Angeline Ball", "The Harrison", True, True, False),
        ("Legends of the 60s Show", "Ulster Hall", True, True, False),
    ],
)
def test_classify(venues, title, venue, hint, is_music, review):
    p = prepare(raw(title=title, venue_name=venue, is_music_hint=hint), venues, create_stubs=False, write_stubs=False)
    verdict = classify(p)
    assert (verdict.publish, verdict.needs_review) == (is_music, review), verdict.reason


def test_venue_aliases_and_rooms(venues):
    assert venues.resolve("SSE Arena Belfast")[0].slug == "the-o2-belfast"
    assert venues.resolve("Ormeau Park, Belfast")[0].slug == "ormeau-park"
    v, room = venues.resolve("Limelight 2")
    assert v.slug == "limelight" and room == "Limelight 2"
    assert venues.resolve("The Deers Head")[0].slug == "deers-head"
    assert venues.resolve("Millennium Forum") is None
