"""Utilities for preparing paper text for LLM consumption."""

import re


# Sections to strip before sending to LLM (case-insensitive, match at line start)
_STRIP_SECTIONS = re.compile(
    r'^(References|Bibliography|Acknowledgments?|Acknowledgements?|Appendix(?:\s+[A-Z])?)[\s:]*$',
    re.MULTILINE | re.IGNORECASE,
)


def prepare_text_for_llm(full_text: str, max_chars: int = 15000) -> str:
    """
    Prepare paper full text for LLM input.

    1. Strip References/Bibliography/Acknowledgments/Appendix sections
    2. Truncate to max_chars at nearest sentence boundary
    """
    if not full_text:
        return ""

    # Find the earliest strippable section and cut there
    match = _STRIP_SECTIONS.search(full_text)
    if match:
        full_text = full_text[:match.start()].rstrip()

    if len(full_text) <= max_chars:
        return full_text

    # Truncate at sentence boundary
    truncated = full_text[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > max_chars // 2:
        return truncated[:last_period + 1]

    return truncated.rstrip()
