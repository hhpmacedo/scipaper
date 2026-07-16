from datetime import datetime, timezone, timedelta
from scipaper.curate.models import Paper, Author


def _p(pid, days_old=0, **kw):
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    return Paper(arxiv_id=pid, title=f"t{pid}", abstract="x",
                 published_date=now - timedelta(days=days_old), **kw)


def test_backlog_merge_and_eligible(tmp_path):
    from scipaper.curate.backlog import Backlog
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    bl = Backlog(tmp_path / "backlog.json")
    bl.merge_new([_p("a", 0), _p("b", 40)], seen_at=now)
    elig = {p.arxiv_id for p in bl.eligible(now=now, within_days=28)}
    assert "a" in elig and "b" not in elig


def test_backlog_roundtrips_paper_fields(tmp_path):
    from scipaper.curate.backlog import Backlog
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    p = _p("a", 1, authors=[Author(name="Jane", affiliation="DeepMind")],
           categories=["cs.RO", "cs.AI"], hf_upvotes=30, citation_count=5)
    Backlog(tmp_path / "b.json").merge_new([p], seen_at=now)
    reloaded = Backlog(tmp_path / "b.json").eligible(now=now, within_days=28)
    assert len(reloaded) == 1
    q = reloaded[0]
    assert q.arxiv_id == "a" and q.title == "ta"
    assert q.categories == ["cs.RO", "cs.AI"]
    assert q.authors[0].name == "Jane" and q.authors[0].affiliation == "DeepMind"
    assert q.hf_upvotes == 30 and q.citation_count == 5
    assert q.published_date is not None


def test_backlog_marks_covered_and_persists(tmp_path):
    from scipaper.curate.backlog import Backlog
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    Backlog(tmp_path / "b.json").merge_new([_p("a", 0)], seen_at=now)
    bl = Backlog(tmp_path / "b.json")
    bl.mark_covered(["a"], week="2026-W29")
    reloaded = Backlog(tmp_path / "b.json")
    assert not any(p.arxiv_id == "a" for p in reloaded.eligible(now=now, within_days=28))


def test_backlog_merge_refreshes_signals(tmp_path):
    from scipaper.curate.backlog import Backlog
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    path = tmp_path / "b.json"
    Backlog(path).merge_new([_p("a", 0, hf_upvotes=5)], seen_at=now)
    Backlog(path).merge_new([_p("a", 0, hf_upvotes=99)], seen_at=now)  # same id, higher signal
    q = [p for p in Backlog(path).eligible(now=now, within_days=28) if p.arxiv_id == "a"][0]
    assert q.hf_upvotes == 99


def test_backlog_degrades_on_corrupt_file(tmp_path):
    from scipaper.curate.backlog import Backlog
    path = tmp_path / "b.json"
    path.write_text("{ not json")
    bl = Backlog(path)  # must not raise
    assert bl.eligible(within_days=28) == []
