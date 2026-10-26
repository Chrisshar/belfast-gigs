import json

from belfast_gigs import benchmark, frontmatter

PAGE = """<html><head>
<script type="application/ld+json">[
 {"@context": "http://schema.org", "@type": "MusicEvent", "name": "Bell X1", "startDate": "2026-12-12T19:00:00",
  "location": {"@type": "Place", "name": "Mandela Hall"}},
 {"@type": "MusicEvent", "name": "Lindisfarne &amp; friends", "startDate": "2027-02-28",
  "location": {"@type": "Place", "name": "Mandela Hall"}},
 {"@type": "MusicEvent", "name": "Some Band", "startDate": "2026-11-20T20:00:00",
  "location": {"@type": "Place", "name": "The Back Room of Somewhere"}},
 {"@type": "MusicEvent", "name": "Andre Rieu", "startDate": "2027-09-09T19:30:00",
  "location": {"@type": "Place", "name": "The SSE Arena"}},
 {"@type": "MusicEvent", "name": "Old Gig", "startDate": "2026-10-01T19:30:00",
  "location": {"@type": "Place", "name": "Mandela Hall"}}
]</script>
<script type="application/ld+json">{"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item":
 {"@type": "Event", "name": "Bell X1", "startDate": "2026-12-12T19:00:00", "location": {"name": "Mandela Hall"}}}]}</script>
</head></html>"""


def test_extract_reads_lists_graphs_and_dedupes():
    items = benchmark.extract(PAGE, "songkick.html")
    assert len(items) == 5
    bell = next(i for i in items if i.name == "Bell X1")
    assert (bell.date, bell.time, bell.venue) == ("2026-12-12", "19:00", "Mandela Hall")
    assert any(i.name == "Lindisfarne & friends" for i in items)


def test_check_sorts_events_into_verdicts(tmp_path):
    inbox, gigs, data = tmp_path / "inbox", tmp_path / "gigs", tmp_path / "data"
    for d in (inbox, gigs, data):
        d.mkdir()
    (inbox / "songkick.html").write_text(PAGE, encoding="utf-8")
    frontmatter.write(
        gigs / "2026-12-12-mandela-hall-bell-x1.md",
        {"id": "a", "title": "Bell X1", "headliner": "Bell X1", "venue": "mandela-hall", "date": "2026-12-12"},
    )
    (data / "tombstones.json").write_text(
        json.dumps([{"fingerprint": "the-o2-belfast|2027-09-09|andre rieu", "reason": "reclassified"}]), encoding="utf-8"
    )
    results = {r.listed.name: r for r in benchmark.check(inbox, "2026-10-26", gigs, data)}
    assert "Old Gig" not in results
    assert results["Bell X1"].verdict == "covered"
    assert results["Lindisfarne & friends"].verdict == "missing"
    assert results["Some Band"].verdict == "unknown_venue"
    assert results["Andre Rieu"].verdict == "removed"
    text = benchmark.report(list(results.values()))
    assert "## Missing at venues we know (1)" in text and "### Mandela Hall (1)" in text
