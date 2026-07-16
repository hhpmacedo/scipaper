"""Curated lab/author prestige signal (stable, version-controlled)."""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_PRESTIGE_PATH = Path("data/prestige.json")


def load_prestige(path: Optional[Path] = None) -> dict:
    """Load the prestige list. Degradable: returns empty lists on any error."""
    path = Path(path) if path else DEFAULT_PRESTIGE_PATH
    try:
        data = json.loads(path.read_text())
        return {"labs": list(data.get("labs", [])), "authors": list(data.get("authors", []))}
    except Exception as e:
        logger.warning(f"Prestige list unavailable ({e}); using empty list")
        return {"labs": [], "authors": []}


def prestige_score(paper, prestige: dict) -> float:
    """1.0 if any author affiliation matches a prestige lab, or author name matches a prestige author; else 0.0."""
    labs = [s.lower() for s in prestige.get("labs", [])]
    authors_list = [s.lower() for s in prestige.get("authors", [])]
    for author in getattr(paper, "authors", []) or []:
        aff = (getattr(author, "affiliation", None) or "").lower()
        if any(lab in aff for lab in labs):
            return 1.0
        name = (getattr(author, "name", None) or "").lower()
        if any(a in name for a in authors_list):
            return 1.0
    return 0.0
