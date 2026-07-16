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


def strip_leading_hook(content: str, hook: str) -> str:
    """
    Remove a leading paragraph that duplicates the hook.

    The generator sometimes emits the hook as the article body's opening
    paragraph, while the hook is also rendered separately. This strips that
    duplicate so it appears once. Content that does not start with the hook
    is returned unchanged.
    """
    if not content or not hook:
        return content

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()

    stripped = content.lstrip()
    # The leading block is everything before the first blank line or heading.
    boundary = re.search(r"\n\s*\n|\n(?=#{1,6}\s)", stripped)
    if boundary:
        lead = stripped[: boundary.start()]
        rest = stripped[boundary.end():]
    else:
        lead, rest = stripped, ""

    # Only a short lead can be a hook (hooks are ~20 words); protects real paragraphs.
    if len(lead.split()) > 40:
        return content

    lead_n, hook_n = _norm(lead), _norm(hook)
    if lead_n and (lead_n == hook_n or lead_n.startswith(hook_n) or hook_n.startswith(lead_n)):
        return rest.lstrip()
    return content
