"""
Adversarial Verification Pipeline

Second-pass fact-checking of generated content against source paper.
"""

from .checker import verify_piece, VerificationReport
from .style import check_style_compliance

__all__ = [
    "verify_piece",
    "VerificationReport",
    "check_style_compliance",
]
