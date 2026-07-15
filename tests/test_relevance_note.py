"""
Tests for the deterministic per-piece "why this, now" relevance note.
"""


def test_relevance_note_summarizes_strongest_signals():
    from scipaper.curate.relevance_note import relevance_note
    from scipaper.curate.models import Paper
    p = Paper(arxiv_id="a", title="t", abstract="x", hf_upvotes=120, citation_count=8)
    note = relevance_note(p)
    assert "120" in note and ("upvote" in note.lower() or "hf" in note.lower())


def test_relevance_note_empty_when_no_signal():
    from scipaper.curate.relevance_note import relevance_note
    from scipaper.curate.models import Paper
    assert relevance_note(Paper(arxiv_id="a", title="t", abstract="x")) == ""


def test_relevance_note_mentions_top_lab():
    from scipaper.curate.relevance_note import relevance_note
    from scipaper.curate.models import Paper, Author
    p = Paper(arxiv_id="a", title="t", abstract="x",
              authors=[Author(name="X", affiliation="Google DeepMind")])
    note = relevance_note(p, prestige={"labs": ["deepmind"], "authors": []})
    assert note != "" and "lab" in note.lower()


def test_relevance_note_caps_number_of_clauses():
    from scipaper.curate.relevance_note import relevance_note
    from scipaper.curate.models import Paper
    p = Paper(arxiv_id="a", title="t", abstract="x", hf_upvotes=120, hn_points=90,
              citation_count=40, github_stars=900, influential_citation_count=15)
    note = relevance_note(p)
    # at most 3 clauses joined (avoid a laundry list)
    assert note.count(",") + note.count(";") <= 2
