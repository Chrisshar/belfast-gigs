"""The Claude classifier (against a fake client: no network, no spend) and whole collect/finish runs."""

from __future__ import annotations

import pickle
import shutil
from types import SimpleNamespace

import pytest
from conftest import NOW, raw

from belfast_gigs import __main__ as cli
from belfast_gigs import frontmatter, llm
from belfast_gigs.adapters import ADAPTERS
from belfast_gigs.adapters.base import Adapter
from belfast_gigs.issues import review_body
from belfast_gigs.llm import Classifier, EventVerdict, Verdicts


class FakeMessages:
    def __init__(self, decide):
        self.decide = decide  # listing dict -> EventVerdict kwargs
        self.calls = []

    def parse(self, **kwargs):
        import json

        self.calls.append(kwargs)
        assert kwargs["model"] == "claude-haiku-5-5" and kwargs["output_format"] is Verdicts
        listings = json.loads(kwargs["messages"][0]["content"].split("\n", 1)[1])
        events = [EventVerdict(id=item["id"], **self.decide(item)) for item in listings]
        usage = SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(parsed_output=Verdicts(events=events), stop_reason="end_turn", usage=usage)


def fake_classifier(tmp_path, monkeypatch, decide):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    c = Classifier(tmp_path, "2026-10")
    c._client = SimpleNamespace(messages=FakeMessages(decide))
    return c


def gig(item):
    return {"is_music": True, "confidence": 0.9, "headliner": item["title"], "support": [], "genres": ["Rock"]}


class TestClassifier:
    def test_batches_caches_and_costs(self, tmp_path, monkeypatch):
        c = fake_classifier(tmp_path, monkeypatch, gig)
        listings = {f"fp{i}": {"title": f"Act {i}"} for i in range(45)}
        out = c.classify(listings, "2026-10-25")
        assert len(out) == 45 and c.calls == 3  # batches of 20
        assert c.month_usage["cost_usd"] == pytest.approx(3 * (1000 * 0.10 + 200 * 0.50) / 1e6)
        c.classify(listings, "2026-10-26")  # all cached now
        assert c.calls == 3

    def test_stops_at_monthly_budget(self, tmp_path, monkeypatch):
        c = fake_classifier(tmp_path, monkeypatch, gig)
        c.month_usage["cost_usd"] = llm.MONTHLY_BUDGET_USD
        assert c.classify({"fp": {"title": "Act"}}, "2026-10-25") == {}
        assert "monthly budget" in c.skipped_reason

    def test_stops_at_per_run_call_cap(self, tmp_path, monkeypatch):
        monkeypatch.setattr(llm, "MAX_CALLS", 1)
        c = fake_classifier(tmp_path, monkeypatch, gig)
        out = c.classify({f"fp{i}": {"title": f"Act {i}"} for i in range(30)}, "2026-10-25")
        assert len(out) == 20 and "per-run limit" in c.skipped_reason

    def test_no_key_means_rules_only(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        c = Classifier(tmp_path, "2026-10")
        assert c.classify({"fp": {"title": "Act"}}, "2026-10-25") == {} and "not set" in c.skipped_reason

    def test_local_runs_use_a_separate_usage_file(self, tmp_path, monkeypatch):
        c = fake_classifier(tmp_path, monkeypatch, gig)
        assert c.usage_path.name == "llm_usage.local.json"
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert Classifier(tmp_path, "2026-10").usage_path.name == "llm_usage.json"

    def test_old_cache_entries_are_pruned(self, tmp_path, monkeypatch):
        c = fake_classifier(tmp_path, monkeypatch, gig)
        c.classify({"old": {"title": "A"}}, "2026-07-01")
        c.classify({"new": {"title": "B"}}, "2026-10-25")
        c.prune_cache("2026-08-26")
        assert set(c.cache) == {"new"}


class FakeAdapter(Adapter):
    name = "fake"
    authority = 1
    events: list = []

    def fetch(self, http):
        return list(self.events)


@pytest.fixture
def fake_source(monkeypatch):
    monkeypatch.setitem(ADAPTERS, "fake", FakeAdapter)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return FakeAdapter


def run_once(site, tmp_path, monkeypatch, decide, *, dry_run=False):
    classifier = fake_classifier(site["data"], monkeypatch, decide)
    monkeypatch.setattr(cli, "Classifier", lambda *a, **k: classifier if k.get("enabled", True) else Classifier(*a, **k))
    collected = cli.collect(["fake"], dry_run=dry_run, venues_dir=site["venues"], data_dir=site["data"], now=NOW, http=object())
    report = cli.finish(collected, dry_run=dry_run, gigs_dir=site["gigs"], venues_dir=site["venues"], data_dir=site["data"])
    return collected, report, classifier


def test_claude_overrules_the_rules_and_fills_genres(site, tmp_path, monkeypatch, fake_source):
    fake_source.events = [
        raw(source="fake", source_key="fake:1", title="Andre Example and his Johann Strauss Orchestra", venue_name="The O2 Belfast", is_music_hint=True),
        raw(source="fake", source_key="fake:2", title="Mystery Night", venue_name="Black Box", is_music_hint=None),
        raw(source="fake", source_key="fake:3", title="UFO", venue_name="Limelight", is_music_hint=False),
    ]

    def decide(item):
        if "Orchestra" in item["title"]:
            return {"is_music": False, "confidence": 0.95, "headliner": "Andre Example", "support": [], "genres": []}
        return {"is_music": True, "confidence": 0.85, "headliner": "Mystery Band", "support": ["Opener"], "genres": ["Punk/Hardcore", "Metal"]}

    _, report, classifier = run_once(site, tmp_path, monkeypatch, decide)
    gigs = {p.stem: frontmatter.read(p)[0] for p in site["gigs"].glob("*.md")}
    [(slug, data)] = gigs.items()  # the orchestra and the club night are out
    assert data["headliner"] == "Mystery Band" and data["support"] == ["Opener"]
    assert data["genres"] == ["Punk/Hardcore", "Metal"]
    assert data["classification"] == {"is_music": True, "confidence": 0.85, "method": "llm"}
    assert "needs_review" not in data
    # The club night was rejected by its source, so Claude was never asked about it.
    sent = classifier._client.messages.calls[0]["messages"][0]["content"]
    assert "UFO" not in sent and "Orchestra" in sent


def test_gig_newly_judged_not_music_is_removed_unless_a_human_edited_it(site, tmp_path, monkeypatch, fake_source):
    fake_source.events = [
        raw(source="fake", source_key="fake:1", title="Andre Example", is_music_hint=True),
        raw(source="fake", source_key="fake:2", title="Other Orchestral Show", date="2026-11-20", is_music_hint=True),
    ]
    run_once(site, tmp_path, monkeypatch, gig)
    assert len(list(site["gigs"].glob("*.md"))) == 2
    edited = site["gigs"] / "2026-11-20-ulster-hall-other-orchestral-show.md"
    data, body = frontmatter.read(edited)
    frontmatter.write(edited, {**data, "locked_fields": ["title"]}, body)

    (site["data"] / "classify_cache.json").unlink()  # pretend these listings are new to Claude
    no = lambda item: {"is_music": False, "confidence": 0.95, "headliner": item["title"], "support": [], "genres": []}  # noqa: E731
    _, report, _ = run_once(site, tmp_path, monkeypatch, no)
    assert report.changes.reclassified == ["2026-11-14-ulster-hall-andre-example"]
    assert [p.name for p in site["gigs"].glob("*.md")] == [edited.name]


def test_unsure_claude_cant_drop_what_the_source_calls_music(site, tmp_path, monkeypatch, fake_source):
    fake_source.events = [raw(source="fake", source_key="fake:1", title="Stop Making Sense Live", is_music_hint=True)]
    doubt = lambda item: {"is_music": False, "confidence": 0.7, "headliner": item["title"], "support": [], "genres": ["Rock"]}  # noqa: E731
    run_once(site, tmp_path, monkeypatch, doubt)
    [path] = site["gigs"].glob("*.md")
    data, _ = frontmatter.read(path)
    assert data["needs_review"] is True and data["classification"]["confidence"] == 0.5


def test_source_and_unsure_claude_agreeing_is_not_flagged(site, tmp_path, monkeypatch, fake_source):
    fake_source.events = [raw(source="fake", source_key="fake:1", title="Little Known Local Band", is_music_hint=True)]
    unsure = lambda item: {"is_music": True, "confidence": 0.6, "headliner": item["title"], "support": [], "genres": ["Rock"]}  # noqa: E731
    run_once(site, tmp_path, monkeypatch, unsure)
    [path] = site["gigs"].glob("*.md")
    assert "needs_review" not in frontmatter.read(path)[0]


def test_allow_titles_override_beats_claude(site, tmp_path, monkeypatch, fake_source):
    (site["data"] / "overrides.yaml").write_text('allow_titles: ["^Andre Example"]\n', encoding="utf-8")
    fake_source.events = [raw(source="fake", source_key="fake:1", title="Andre Example", is_music_hint=None)]
    no = lambda item: {"is_music": False, "confidence": 0.99, "headliner": item["title"], "support": [], "genres": []}  # noqa: E731
    run_once(site, tmp_path, monkeypatch, no)
    assert len(list(site["gigs"].glob("*.md"))) == 1


def test_reclassified_gig_that_returns_keeps_first_seen_and_backfill(site, tmp_path, monkeypatch, fake_source):
    fake_source.events = [raw(source="fake", source_key="fake:1", title="Andre Example", is_music_hint=None)]
    run_once(site, tmp_path, monkeypatch, gig)  # first run: backfill
    [path] = site["gigs"].glob("*.md")
    original = frontmatter.read(path)[0]
    assert original["backfill"] is True
    no = lambda item: {"is_music": False, "confidence": 0.95, "headliner": item["title"], "support": [], "genres": []}  # noqa: E731
    (site["data"] / "classify_cache.json").unlink()
    run_once(site, tmp_path, monkeypatch, no)
    assert list(site["gigs"].glob("*.md")) == []
    (site["data"] / "classify_cache.json").unlink()
    run_once(site, tmp_path, monkeypatch, gig)
    [path] = site["gigs"].glob("*.md")
    back = frontmatter.read(path)[0]
    assert back["id"] == original["id"] and back["first_seen"] == original["first_seen"] and back["backfill"] is True


def test_dry_run_writes_nothing_but_records_spend(site, tmp_path, monkeypatch, fake_source):
    fake_source.events = [raw(source="fake", source_key="fake:1", is_music_hint=None)]
    run_once(site, tmp_path, monkeypatch, gig, dry_run=True)
    assert list(site["gigs"].glob("*.md")) == []
    assert (site["data"] / "llm_usage.local.json").exists()
    assert not (site["data"] / "classify_cache.json").exists() and not (site["data"] / "seen.json").exists()


def test_saved_run_reapplies_onto_a_newer_checkout(site, tmp_path, monkeypatch, fake_source):
    """CI's push-conflict path: reset to the newer main, apply the saved run, no re-scrape."""
    fake_source.events = [raw(source="fake", source_key="fake:1", venue_name="Some New Bar", address="1 Example St, Belfast BT1 1AA")]
    collected, _, _ = run_once(site, tmp_path, monkeypatch, gig)
    saved = pickle.dumps(collected)

    fresh = {k: tmp_path / "fresh" / k for k in ("gigs", "venues", "data")}
    shutil.copytree(site["venues"], fresh["venues"])
    (fresh["venues"] / "some-new-bar.md").unlink()  # the newer main doesn't have our stub yet
    fresh["gigs"].mkdir()
    fresh["data"].mkdir()
    frontmatter.write(fresh["gigs"] / "cms-added.md", {"id": "22222222-2222-4222-8222-222222222222", "title": "Hand Added", "headliner": "Hand Added", "venue": "black-box", "date": "2026-12-01", "first_seen": "2026-10-25T10:00:00Z"})

    report = cli.finish(pickle.loads(saved), gigs_dir=fresh["gigs"], venues_dir=fresh["venues"], data_dir=fresh["data"])
    assert report.changes.created and (fresh["venues"] / "some-new-bar.md").exists()
    assert (fresh["gigs"] / "cms-added.md").exists()  # the CMS edit made meanwhile survives
    assert (fresh["data"] / "classify_cache.json").exists()


def test_failed_source_counts_towards_broken_issue(site, tmp_path, monkeypatch, fake_source):
    fake_source.events = []
    for _ in range(2):
        _, report, _ = run_once(site, tmp_path, monkeypatch, gig)
    health = frontmatter.yaml.safe_load((site["data"] / "source_health.json").read_text())
    assert health["fake"]["consecutive_failures"] == 2 and report.sources[0].status == "failed"


def test_review_issue_body_lists_flagged_gigs_and_venues(site):
    frontmatter.write(site["gigs"] / "a.md", {"id": "x", "headliner": "Maybe Band", "venue": "black-box", "needs_review": True, "classification": {"is_music": True, "confidence": 0.5, "method": "rules"}})
    body = review_body(site["gigs"], site["venues"], ["a: might duplicate b"], [])
    assert "Maybe Band" in body and "rules, confidence 0.5" in body and "might duplicate" in body
    assert "mandela-hall" in body  # seed venue still flagged for review
    empty_gigs, empty_venues = site["gigs"] / "none", site["venues"] / "none"
    empty_gigs.mkdir()
    empty_venues.mkdir()
    assert review_body(empty_gigs, empty_venues, [], []) is None
