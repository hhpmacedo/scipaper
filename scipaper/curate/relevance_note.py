"""
Deterministic per-piece "why this, now" line built from the paper's own
traction/quality signals (HF upvotes, HN points, Reddit score, early/influential
citations, GitHub stars, prestige-lab membership).

No LLM involved: cheaper and always grounded in a concrete number or fact.
Returns "" when no signal clears its threshold, so the renderer shows nothing.
"""
from typing import Optional

# Minimum values before a signal is considered notable enough to surface.
HF_UPVOTES_THRESHOLD = 20
HN_POINTS_THRESHOLD = 20
GITHUB_STARS_THRESHOLD = 100
INFLUENTIAL_CITATIONS_THRESHOLD = 3
EARLY_CITATIONS_THRESHOLD = 5
REDDIT_SCORE_THRESHOLD = 30

MAX_CLAUSES = 3


def relevance_note(paper, prestige: Optional[dict] = None) -> str:
    """
    A short grounded reason a paper is worth the reader's time, built from
    its actual traction/quality signals. Returns "" when no signal clears
    threshold. Picks at most the MAX_CLAUSES strongest clauses (avoid a
    laundry list).
    """
    clauses = []  # list of (priority, text)

    hf_upvotes = getattr(paper, "hf_upvotes", 0) or 0
    if hf_upvotes >= HF_UPVOTES_THRESHOLD:
        clauses.append((hf_upvotes, f"{hf_upvotes} upvotes on Hugging Face Papers"))

    hn_points = getattr(paper, "hn_points", 0) or 0
    if hn_points >= HN_POINTS_THRESHOLD:
        clauses.append((hn_points, f"{hn_points} points on Hacker News"))

    github_stars = getattr(paper, "github_stars", 0) or 0
    if github_stars >= GITHUB_STARS_THRESHOLD:
        clauses.append((github_stars, f"{github_stars} GitHub stars"))

    influential = getattr(paper, "influential_citation_count", 0) or 0
    citations = getattr(paper, "citation_count", 0) or 0
    if influential >= INFLUENTIAL_CITATIONS_THRESHOLD:
        # Weight influential citations heavily — they're the strongest signal.
        clauses.append((influential * 5, f"{influential} influential citations already"))
    elif citations >= EARLY_CITATIONS_THRESHOLD:
        clauses.append((citations, f"{citations} early citations"))

    reddit_score = getattr(paper, "reddit_score", 0) or 0
    if reddit_score >= REDDIT_SCORE_THRESHOLD:
        clauses.append((reddit_score, "trending on r/MachineLearning"))

    # Prestige-lab membership: lowest priority, appended only if there's room.
    from_top_lab = False
    if prestige is not None:
        from .prestige import prestige_score
        from_top_lab = prestige_score(paper, prestige) >= 1.0

    clauses.sort(key=lambda c: c[0], reverse=True)
    texts = [text for _, text in clauses[:MAX_CLAUSES]]
    if from_top_lab and len(texts) < MAX_CLAUSES:
        texts.append("from a top lab")

    if not texts:
        return ""
    return "Why now: " + ", ".join(texts) + "."
