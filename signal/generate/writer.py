"""
Citation-grounded content generation.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from ..curate.models import Paper

logger = logging.getLogger(__name__)


@dataclass
class Piece:
    """A generated piece for the newsletter."""
    paper_id: str
    title: str
    hook: str
    content: str  # Full piece with inline citations
    word_count: int
    citations: list  # List of {section, claim} pairs
    
    # Metadata
    generated_at: str
    model_used: str
    
    # Verification status
    verified: bool = False
    verification_report: Optional[dict] = None


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
"""


@dataclass
class GenerationConfig:
    """Configuration for content generation."""
    llm_model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 2000
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
    
    # TODO: Implement generation
    #
    # 1. Format prompts with paper content
    # 2. Call LLM API
    # 3. Parse response
    # 4. Extract citations
    # 5. Build Piece object
    
    logger.info(f"Generating piece for {paper.arxiv_id}")
    raise NotImplementedError("Content generation not yet implemented")


def extract_citations(content: str) -> list:
    """
    Extract citation references from generated content.
    
    Looks for patterns like [§3.2], [Abstract], [Table 1], [Figure 3]
    
    Returns list of (claim_text, citation_ref) tuples.
    """
    import re
    
    # Match citations in format [§X.Y] or [Abstract] or [Table N] or [Figure N]
    pattern = r'([^.!?]+)\s*\[(§[\d.]+|Abstract|Table\s+\d+|Figure\s+\d+)\]'
    
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
        
        # Check if section exists
        if ref.startswith("§"):
            section = ref[1:]  # Remove §
            # Look for section header
            if section not in full_text and f"Section {section}" not in full_text:
                invalid.append(cit)
        
        # Tables and figures harder to validate without parsed structure
        # For now, just check the reference pattern exists
        elif ref.startswith("Table") or ref.startswith("Figure"):
            if ref not in full_text:
                invalid.append(cit)
    
    return invalid
