"""
Citation-grounded content generation.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..config import DEFAULT_GENERATION_MODEL
from ..curate.models import Paper
from ..retry import api_retry
from ..text_utils import prepare_text_for_llm

logger = logging.getLogger(__name__)


@dataclass
class Piece:
    """A generated piece for the newsletter."""
    paper_id: str
    title: str
    hook: str
    content: str  # Full piece with inline citations
    word_count: int
    citations: list  # List of {claim, citation} dicts

    # Metadata
    generated_at: str
    model_used: str

    # Paper metadata for display
    paper_url: str = ""
    authors: list = None  # List of author name strings

    # Verification status
    verified: bool = False
    verification_report: Optional[dict] = None

    def __post_init__(self):
        if self.authors is None:
            self.authors = []


GENERATION_SYSTEM_PROMPT = """You are a writer for Signal, a newsletter that explains AI research to technically literate non-researchers.

Your task is to transform a research paper into an 800-1200 word piece that is:
- Rigorous but accessible (Quanta Magazine level)
- Zero hype, zero speculation
- Concrete over abstract
- Honest about limitations

CRITICAL REQUIREMENT: Every factual claim must cite a specific passage from the paper.
Use this format: "claim text [§X.Y]" or "[Abstract]" or "[Table N]" or "[Figure N]"

If you cannot ground a claim to a specific passage, DO NOT include it.

STRUCTURE (follow exactly):
1. Hook (1 sentence): The surprising thing from this paper
2. The Problem (2-3 paragraphs): What were they solving? Why is it hard?
3. What They Did (3-4 paragraphs): The actual approach, with concrete examples
4. The Results (2-3 paragraphs): What worked, what didn't, key numbers with context
5. Why It Matters (1-2 paragraphs): Implications for practitioners, grounded not speculative

STYLE RULES:
- Never use: revolutionary, groundbreaking, game-changing, breakthrough
- Explain technical terms in parentheses or avoid them
- Every abstract concept needs a concrete example within 2 sentences
- Include limitations section
- Tone: curious and engaged, not breathless

Reader profile: Software engineer who uses AI tools daily but doesn't read papers. They understand ML basics but not architecture details. They want to understand what's happening, not just what to think.

Return your response as JSON:
{
  "title": "piece title",
  "hook": "one sentence hook",
  "content": "the full piece with citations",
  "sections": ["The Problem", "What They Did", "The Results", "Why It Matters"]
}
"""


GENERATION_USER_PROMPT = """Write a Signal piece for this paper.

PAPER TITLE: {title}

PAPER FULL TEXT:
{full_text}

Remember:
- Every claim must have a citation [§X.Y]
- 800-1200 words
- Follow the exact structure
- No hype, concrete examples, honest about limitations
- Return as JSON with title, hook, content, and sections fields
"""


@dataclass
class GenerationConfig:
    """Configuration for content generation."""
    llm_provider: str = "anthropic"
    llm_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.3  # Lower for more consistent output


async def generate_piece(
    paper: Paper,
    config: Optional[GenerationConfig] = None
) -> Piece:
    """
    Generate a citation-grounded piece from a paper.

    Stage 1 of the content pipeline:
    1. Parse paper PDF to get full text
    2. Call LLM with generation prompt
    3. Extract and validate citations
    4. Return piece ready for verification

    Returns Piece object (not yet verified).
    """
    config = config or GenerationConfig()

    if not paper.full_text:
        raise ValueError(f"Paper {paper.arxiv_id} has no full text. Parse PDF first.")

    logger.info(f"Generating piece for {paper.arxiv_id}")

    user_prompt = GENERATION_USER_PROMPT.format(
        title=paper.title,
        full_text=prepare_text_for_llm(paper.full_text),
    )

    try:
        if config.llm_provider == "anthropic":
            response_text = await _generate_with_anthropic(user_prompt, config)
        elif config.llm_provider == "openai":
            response_text = await _generate_with_openai(user_prompt, config)
        else:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider}")
    except Exception as e:
        logger.error(f"LLM generation failed for {paper.arxiv_id}: {e}")
        raise

    # Parse the response
    parsed = _parse_generation_response(response_text)

    content = parsed.get("content", response_text)
    citations = extract_citations(content)
    invalid = validate_citations(citations, paper.full_text)

    if invalid:
        logger.warning(
            f"{len(invalid)} invalid citations in piece for {paper.arxiv_id}"
        )

    piece = Piece(
        paper_id=paper.arxiv_id,
        title=parsed.get("title", paper.title),
        hook=parsed.get("hook", ""),
        content=content,
        word_count=len(content.split()),
        citations=citations,
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_used=config.llm_model or DEFAULT_GENERATION_MODEL,
        paper_url=paper.pdf_url or f"https://arxiv.org/abs/{paper.arxiv_id}",
        authors=[a.name for a in paper.authors],
    )

    logger.info(
        f"Generated piece for {paper.arxiv_id}: "
        f"{piece.word_count} words, {len(citations)} citations"
    )

    return piece


@api_retry
async def _generate_with_anthropic(prompt: str, config: GenerationConfig) -> str:
    """Generate content using Anthropic API."""
    import anthropic

    model = config.llm_model or DEFAULT_GENERATION_MODEL
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        system=GENERATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


@api_retry
async def _generate_with_openai(prompt: str, config: GenerationConfig) -> str:
    """Generate content using OpenAI API."""
    from openai import AsyncOpenAI

    model = config.llm_model or DEFAULT_GENERATION_MODEL
    client = AsyncOpenAI(api_key=config.openai_api_key)
    response = await client.chat.completions.create(
        model=model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        messages=[
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content


def _parse_generation_response(text: str) -> dict:
    """Parse LLM response, handling both JSON and plain text."""
    text = text.strip()

    # Try JSON extraction
    if "```" in text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the response
    match = re.search(r'\{[^{}]*"content"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fall back to treating entire response as content
    # Try to extract hook (first sentence)
    sentences = text.split(". ")
    hook = sentences[0] + "." if sentences else ""

    return {
        "title": "",
        "hook": hook,
        "content": text,
    }


def extract_citations(content: str) -> list:
    """
    Extract citation references from generated content.

    Looks for patterns like [§3.2], [Abstract], [Table 1], [Figure 3]

    Returns list of {claim, citation} dicts.
    """
    # Match citations in format [§X.Y] or [Abstract] or [Table N] or [Figure N]
    pattern = r'([^.\n!?]*?)\s*\[(§[\d.]+|Abstract|Table\s+\d+|Figure\s+\d+)\]'

    matches = re.findall(pattern, content)

    return [{"claim": claim.strip(), "citation": ref} for claim, ref in matches]


def validate_citations(citations: list, full_text: str) -> list:
    """
    Validate that each citation reference exists in the paper.

    Returns list of invalid citations.
    """
    invalid = []

    for cit in citations:
        ref = cit["citation"]

        if ref == "Abstract":
            # Abstract is always valid
            continue

        # Check if section exists
        if ref.startswith("§"):
            section = ref[1:]  # Remove §
            # Look for section number in text (e.g., "3.2" or "Section 3.2")
            if (
                section not in full_text
                and f"Section {section}" not in full_text
                and f"{section} " not in full_text
            ):
                invalid.append(cit)

        # Tables and figures
        elif ref.startswith("Table") or ref.startswith("Figure"):
            if ref not in full_text and ref.lower() not in full_text.lower():
                invalid.append(cit)

    return invalid
