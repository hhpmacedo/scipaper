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
from .pdf_parser import ParsedPaper

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

    # Structured abstract (3-part: what_they_did, key_result, why_it_matters)
    structured_abstract: Optional[dict] = None

    # Hero figure (lead piece only)
    hero_figure_url: Optional[str] = None
    hero_figure_caption: Optional[str] = None

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
5. Why It Matters (1-2 paragraphs): Forward-looking implications ONLY — see rules below

AVOIDING REDUNDANCY (critical):
- The "structured_abstract" (Signal box) appears ABOVE your content. Readers see it first.
- Do NOT open the content by restating the hook or the key result. Start "The Problem" directly.
- "Why It Matters" must be ADDITIVE — new implications, connections to the broader field, or practitioner actions. It must NOT restate the key result, the hook, or the structured abstract. If you find yourself writing the same takeaway again, cut it.
- If a specific number appears in the title, it MUST match the body. Pick one number and use it consistently throughout title, hook, structured_abstract, and content.

STYLE RULES:
- Never use: revolutionary, groundbreaking, game-changing, breakthrough
- Explain technical terms in parentheses or avoid them
- Every abstract concept needs a concrete example within 2 sentences
- Weave limitations into the body naturally (e.g. in Results or Why It Matters) rather than always ending with a caveat paragraph. Vary your endings — some pieces can end with an implication, a comparison, or a forward-looking question. Not every piece needs to close with "but this is just a lab result."
- Tone: curious and engaged, not breathless

TECHNICAL DEPTH:
- "What They Did" should focus on the approach at a level your reader can act on or explain to a colleague. Prioritize the "so what" over the mechanism.
- Cut implementation details that only matter to someone reimplementing the paper (algorithm line numbers, mathematical derivations, specific optimizer choices). Keep details that change how a practitioner thinks about the problem.
- If you need more than one sentence to explain a mechanism, that's a signal to simplify or cut it.

Reader profile: Software engineer who uses AI tools daily but doesn't read papers. They understand ML basics but not architecture details. They want to understand what's happening, not just what to think.

Return your response as JSON:
{
  "title": "piece title",
  "hook": "one sentence hook",
  "structured_abstract": {
    "what_they_did": "1-2 sentences: what the researchers actually built or tested",
    "key_result": "1-2 sentences: the most important finding, with a concrete number if possible",
    "why_it_matters": "1 sentence: what this means for practitioners — must differ from Why It Matters section"
  },
  "content": "the full piece with citations — do NOT repeat the hook or structured_abstract content",
  "sections": ["The Problem", "What They Did", "The Results", "Why It Matters"],
  "hero_figure": null or <integer figure number>
}

For hero_figure: Pick the single most impactful figure number (e.g. 1, 3) from the paper that best illustrates the key result. Return null if no figure is compelling enough or if the paper has no figures worth highlighting.
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
    config: Optional[GenerationConfig] = None,
    parsed_paper: Optional[ParsedPaper] = None,
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

    # Match hero figure selection to extracted figures
    hero_figure_caption = None
    selected_figure = None
    hero_fig_num = parsed.get("hero_figure")
    if hero_fig_num is not None and parsed_paper and parsed_paper.figures:
        for fig in parsed_paper.figures:
            if fig.index == hero_fig_num:
                selected_figure = fig
                hero_figure_caption = fig.caption or f"Figure {fig.index}"
                break

    # Parse structured abstract (validate keys)
    raw_abstract = parsed.get("structured_abstract")
    structured_abstract = None
    if isinstance(raw_abstract, dict):
        structured_abstract = {
            "what_they_did": raw_abstract.get("what_they_did", ""),
            "key_result": raw_abstract.get("key_result", ""),
            "why_it_matters": raw_abstract.get("why_it_matters", ""),
        }

    piece = Piece(
        paper_id=paper.arxiv_id,
        title=parsed.get("title", paper.title),
        hook=parsed.get("hook", ""),
        structured_abstract=structured_abstract,
        content=content,
        word_count=len(content.split()),
        citations=citations,
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_used=config.llm_model or DEFAULT_GENERATION_MODEL,
        paper_url=paper.pdf_url or f"https://arxiv.org/abs/{paper.arxiv_id}",
        authors=[a.name for a in paper.authors],
        hero_figure_caption=hero_figure_caption,
    )
    # Attach the selected figure object for the pipeline to save later
    piece._hero_figure = selected_figure

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
