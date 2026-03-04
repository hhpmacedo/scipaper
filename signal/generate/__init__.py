"""
Content Generation Pipeline

Transforms papers into publication-ready pieces with citation grounding.
"""

from .writer import generate_piece
from .pdf_parser import parse_paper_pdf
from .edition import assemble_edition

__all__ = [
    "generate_piece",
    "parse_paper_pdf",
    "assemble_edition",
]
