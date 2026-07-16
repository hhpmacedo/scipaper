"""
Tests for the curated prestige (labs/authors) signal.
"""


def test_load_prestige_reads_file(tmp_path):
    import json
    from scipaper.curate.prestige import load_prestige
    p = tmp_path / "prestige.json"
    p.write_text(json.dumps({"labs": ["openai"], "authors": ["jane doe"]}))
    data = load_prestige(p)
    assert "openai" in data["labs"] and "jane doe" in data["authors"]


def test_load_prestige_degrades_on_missing_or_corrupt(tmp_path):
    from scipaper.curate.prestige import load_prestige
    missing = load_prestige(tmp_path / "nope.json")
    assert missing == {"labs": [], "authors": []}
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    assert load_prestige(bad) == {"labs": [], "authors": []}


def test_prestige_score_matches_lab_affiliation():
    from scipaper.curate.prestige import prestige_score
    from scipaper.curate.models import Paper, Author
    prestige = {"labs": ["deepmind"], "authors": []}
    hit = Paper(arxiv_id="a", title="t", abstract="x",
                authors=[Author(name="A", affiliation="Google DeepMind")])
    miss = Paper(arxiv_id="b", title="t", abstract="x",
                 authors=[Author(name="B", affiliation="Some Startup")])
    assert prestige_score(hit, prestige) == 1.0
    assert prestige_score(miss, prestige) == 0.0


def test_prestige_score_empty_prestige_is_zero():
    from scipaper.curate.prestige import prestige_score
    from scipaper.curate.models import Paper, Author
    p = Paper(arxiv_id="a", title="t", abstract="x", authors=[Author(name="A", affiliation="DeepMind")])
    assert prestige_score(p, {"labs": [], "authors": []}) == 0.0
