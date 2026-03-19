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

    # Executive off-ramp: 2-3 sentences answering what capability is emerging,
    # how mature it is, and what decision it informs. Sits between hook and body.
    signal_block: Optional[str] = None

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

Your task is to transform a research paper into an 800-1000 word piece (hard cap: 1000 words) that is:
- Rigorous but accessible (Quanta Magazine level)
- Zero hype, zero speculation
- Concrete over abstract
- Honest about limitations — stated in both technical and practical terms

CRITICAL REQUIREMENT: Every factual claim must cite a specific passage from the paper.
Use this format: "claim text [§X.Y]" or "[Abstract]" or "[Table N]" or "[Figure N]"

If you cannot ground a claim to a specific passage, DO NOT include it.

═══════════════════════════════════════
STRUCTURE (follow exactly, with word budgets):
═══════════════════════════════════════

1. Hook (1 sentence, ~20 words)
   - Must state a capability or finding: what can now be done that couldn't before, or what assumption just got challenged.
   - NEVER start with a method description ("researchers propose", "we present", "this paper introduces").
   - BAD: "Researchers propose a method to identify which AI model wrote a piece of code."
   - GOOD: "You can now identify which specific AI model wrote a piece of code — with 87% accuracy."

2. Signal Block (2-3 sentences, ~60 words)
   - Visually separated executive summary. Answers three questions in order:
     a) What capability is emerging from this work?
     b) How mature is it? (lab proof-of-concept / pattern emerging / actionable today)
     c) What decision does it inform for practitioners?
   - Example: "Code-level model attribution is now feasible in controlled settings — you can identify which AI wrote a specific snippet. Production-ready tools are 2-3 years out, but organizations building AI governance frameworks should be tracking this. Dataset and code are public."
   - This is NOT a summary of the method. It is the practitioner's filter.

3. The Problem (~150 words, 2-3 paragraphs)
   - What were they trying to solve? Why is it hard? Why does it matter?

4. What They Did (~250 words, 3-4 paragraphs)
   - The actual approach, explained concretely.
   - Every named technique, loss function, or abstraction must be followed within two sentences by a concrete example or analogy of what it does in practice.
   - BAD: "The model uses contrastive learning to align representations."
   - GOOD: "The model uses contrastive learning — a training approach that works like showing a dog two photos and teaching it that 'these two are the same breed, these two aren't' — to pull similar code patterns together in its internal representation."
   - If a paper has multiple contributions, pick the primary one and compress the others to 1-2 sentences each.

5. The Results (~150 words, 2-3 paragraphs)
   - REQUIRED: At least one specific, concrete finding that lets the reader gauge magnitude.
   - If the paper has benchmark numbers: quote them with a baseline. "DCAN achieves 87% attribution accuracy, compared to 62% for the best existing method."
   - If the paper has NO benchmark numbers (e.g. interpretability, theoretical, or qualitative work): state a specific qualitative finding with concrete detail, then explicitly note "This paper reports no benchmark comparisons — [reason, e.g. 'the contribution is a method, not a performance claim']."
   - UNACCEPTABLE: "reliable attribution performance across diverse settings", "substantially higher fidelity", "measurable fraction" — these are paraphrases, not results.
   - What worked, what didn't. Honest about limitations.
   - Every limitation must be dual-framed: what's technically incomplete (for builders) AND what that means for production timelines (for decision-makers).
   - BAD: "The benchmark covers only four LLMs and four languages."
   - GOOD: "The benchmark covers only four LLMs and four languages — production codebases with mixed model usage and human edits are a harder problem, likely 2-3 years from reliable tooling."

6. Why It Matters (~120 words, 1-2 paragraphs)
   - Implications for practitioners. Grounded, not speculative.
   - Include one sentence positioning the work on a maturity spectrum: lab proof-of-concept, pattern emerging in production frameworks, or actionable today.
   - Every implication must trace back to something the paper demonstrated.

═══════════════════════════════════════
AUDIENCE CEILING — HARD RULE
═══════════════════════════════════════

Reader profile: Software engineer or PM who uses AI tools daily but does not read papers.

They KNOW: APIs, basic ML concepts (training, validation, models, datasets), statistical terms, GPU.
They DO NOT KNOW: transformer internals, attention mechanisms, specific architectures, math notation.

Any concept beyond this ceiling must be explained via analogy or concrete illustration BEFORE the technical name, not after.
- BAD: "The model's attention heads attend to query positions..."
- GOOD: "Think of it as eye-tracking for the model's internal processing — a score that measures how much of the model's computational focus is directed at the image versus boilerplate instructions (technically: attention head activations across query positions)."

═══════════════════════════════════════
STYLE RULES
═══════════════════════════════════════

NEVER use: revolutionary, groundbreaking, game-changing, breakthrough, incredible, amazing, novel, utilize, leverage, state-of-the-art, obviously, clearly, very, really, actually, basically.

VOICE — DO:
- State findings directly. "DCAN achieves 87% accuracy" — not "The paper reports that DCAN achieves 87% accuracy."
- Name limitations concretely. "Four models, four languages, controlled conditions" — not "several limitations deserve attention."
- Frame implications as conditional. "If your organization needs to audit AI-generated code..." — not "This will change how organizations..."
- Use the paper's own hedging when authors hedge. Quote "≈" rather than "=" when the paper does this.

VOICE — NEVER:
- Quote the paper's self-characterizations in Results. Never: "reliable," "significant," "state-of-the-art" — always give the actual number.
- Speculate beyond the paper's claims in Why It Matters.
- Drop jargon without grounding it within two sentences.
- List more than 3 model names. "Ten 7B-parameter vision-language models" suffices over naming all of them.
- Explain the same concept twice across sections.

═══════════════════════════════════════
RETURN FORMAT
═══════════════════════════════════════

Return your response as JSON:
{
  "title": "piece title (8-12 words)",
  "hook": "one sentence hook — capability or finding, not method",
  "signal_block": "2-3 sentences: capability emerging, maturity level, decision it informs",
  "structured_abstract": {
    "what_they_did": "1-2 sentences: what the researchers actually built or tested",
    "key_result": "1-2 sentences: the most important finding, with a concrete number",
    "why_it_matters": "1 sentence: what this means for practitioners, grounded not speculative"
  },
  "content": "the full piece with citations — Hook paragraph, then ## The Problem, ## What They Did, ## The Results, ## Why It Matters",
  "sections": ["The Problem", "What They Did", "The Results", "Why It Matters"],
  "hero_figure": null or <integer figure number>
}

NOTE: The signal_block does NOT appear inside "content". It is rendered separately between the hook and the article body.

For hero_figure: Pick the single most impactful figure number (e.g. 1, 3) from the paper that best illustrates the key result. Return null if no figure is compelling enough.
"""


GENERATION_USER_PROMPT = """Write a Signal piece for this paper.

PAPER TITLE: {title}

PAPER FULL TEXT:
{full_text}

Remember:
- Hook = capability or finding (never a method description)
- Signal block = 2-3 sentences: what capability, how mature, what decision
- Every claim must have a citation [§X.Y]
- Results section must include at least one specific number with baseline
- Every limitation dual-framed: technical gap + production timeline implication
- 800-1000 words, hard cap 1000
- Return as JSON with all fields including signal_block
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
        signal_block=parsed.get("signal_block", "") or "",
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
