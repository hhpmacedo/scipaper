"""
Publishing Pipeline

Delivers editions via email and web archive.
"""

from .email import send_edition_email
from .web import generate_web_archive

__all__ = [
    "send_edition_email",
    "generate_web_archive",
]
