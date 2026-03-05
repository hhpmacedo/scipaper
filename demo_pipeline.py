"""
Demo: trace a sample paper through the full Signal pipeline.

Run with: python demo_pipeline.py
"""

import asyncio
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Avoid stdlib signal collision
loop = asyncio.new_event_loop()

from signal.curate.models import AnchorDocument, Author, Paper
from signal.curate.score import ScoringConfig, score_relevance, score_narrative_potential
from signal.curate.select import SelectionConfig, select_edition_papers, get_runners_up
from signal.generate.writer import GenerationConfig, generate_piece, extract_citations
from signal.verify.checker import VerificationConfig, verify_piece
from signal.verify.style import StyleConfig, check_style_compliance
from signal.generate.edition import AssemblyConfig, assemble_edition, generate_edition_subject
from signal.publish.email import render_edition_html, render_edition_text
from signal.publish.web import WebConfig, generate_edition_page, generate_rss_feed


# ── Sample data ──────────────────────────────────────────────────────

SAMPLE_PAPER = Paper(
    arxiv_id="2403.19887",
    title="ReasonAgent: Reinforcement Learning for Reasoning in Large Language Models",
    abstract=(
        "We introduce ReasonAgent, a reinforcement learning framework that teaches "
        "large language models to reason through multi-step problems. Unlike chain-of-thought "
        "prompting which relies on in-context examples, ReasonAgent learns a reasoning policy "
        "through trial-and-error on mathematical and logical tasks. On GSM8K, our approach "
        "achieves 89.2% accuracy (vs 78.1% for CoT prompting), while on ARC-Challenge it "
        "reaches 71.4%. Notably, the learned reasoning strategy transfers across tasks — "
        "a policy trained on math generalizes to logical reasoning with only 12% degradation. "
        "We also find that smaller models (7B) with ReasonAgent match the performance of "
        "much larger models (70B) using standard prompting."
    ),
    authors=[
        Author(name="Sarah Chen", affiliation="Stanford CS"),
        Author(name="Marcus Williams", affiliation="Google DeepMind"),
        Author(name="Priya Patel", affiliation="Stanford CS"),
    ],
    categories=["cs.AI", "cs.LG"],
    published_date=datetime(2025, 3, 1),
    pdf_url="https://arxiv.org/pdf/2403.19887",
    citation_count=12,
    hn_points=87,
    full_text="""Abstract
We introduce ReasonAgent, a reinforcement learning framework that teaches
large language models to reason through multi-step problems. Unlike chain-of-thought
prompting which relies on in-context examples, ReasonAgent learns a reasoning policy
through trial-and-error on mathematical and logical tasks. On GSM8K, our approach
achieves 89.2% accuracy (vs 78.1% for CoT prompting), while on ARC-Challenge it
reaches 71.4%. Notably, the learned reasoning strategy transfers across tasks.

1 Introduction
Multi-step reasoning remains one of the key challenges for large language models.
While chain-of-thought (CoT) prompting has improved reasoning performance,
it depends heavily on the quality of in-context examples and does not learn from
mistakes. We propose a different paradigm: treating reasoning as a sequential
decision-making problem and applying reinforcement learning.

2 Methods
ReasonAgent uses proximal policy optimization (PPO) to train a reasoning policy
on top of a frozen language model. The policy network learns to decompose
problems into sub-steps, verify intermediate results, and backtrack when needed.

2.1 Architecture
The reasoning policy is a lightweight transformer adapter (45M parameters) that
sits on top of the base LLM. It outputs reasoning actions: DECOMPOSE, VERIFY,
SOLVE, and BACKTRACK. The base LLM generates text conditioned on these actions.

2.2 Training
We train on a curriculum of 50,000 problems spanning arithmetic, algebra,
geometry, and logic. The reward signal is binary: correct or incorrect final answer.
We use PPO with a KL penalty to prevent the policy from diverging too far
from the base model's reasoning distribution.

3 Results
Table 1 summarizes our main results across four benchmarks.

Table 1: ReasonAgent results vs baselines
GSM8K: ReasonAgent 89.2%, CoT 78.1%, Standard 64.3%
ARC-Challenge: ReasonAgent 71.4%, CoT 63.2%, Standard 52.1%
MATH: ReasonAgent 47.8%, CoT 38.4%, Standard 22.1%
LogiQA: ReasonAgent 68.9%, CoT 61.7%, Standard 55.3%

Figure 1 shows the learning curve during training.
Figure 1: Training progression showing accuracy improvement over episodes.

3.1 Transfer Learning
A surprising finding is that reasoning policies transfer across domains.
A policy trained exclusively on GSM8K math problems achieves 63.1% on
ARC-Challenge (vs 71.4% with direct training) — only 12% degradation
despite never seeing logical reasoning problems.

3.2 Model Size Effects
Figure 2 compares performance across model sizes.
Figure 2: ReasonAgent performance by model size.

A 7B model with ReasonAgent (89.2% on GSM8K) matches a 70B model
using standard prompting (88.7%). This suggests that learned reasoning
strategies can compensate for raw model capacity.

4 Limitations
ReasonAgent requires significant compute for the RL training phase
(approximately 200 GPU-hours on A100s for the 7B model). The approach
also struggles with problems requiring very long reasoning chains
(>15 steps), where the policy tends to loop. We have not yet tested
on models larger than 70B parameters.

5 Related Work
Our work builds on chain-of-thought prompting and self-consistency,
but differs fundamentally in that our approach learns rather than
prompts reasoning behavior.

6 Conclusion
ReasonAgent demonstrates that reinforcement learning can teach language
models to reason more effectively than prompting-based approaches. The
transfer of reasoning strategies across domains is a promising direction
for building generally capable reasoning systems.""",
)

# More papers for selection demo
OTHER_PAPERS = [
    Paper(
        arxiv_id="2403.19901",
        title="FlashDecoding: Hardware-Aware Attention for 10x Faster LLM Inference",
        abstract="We present FlashDecoding, a hardware-aware attention implementation that achieves 10x speedup for LLM inference on consumer GPUs by exploiting memory hierarchy.",
        authors=[Author(name="Wei Liu", affiliation="Meta AI")],
        categories=["cs.LG", "cs.PF"],
        published_date=datetime(2025, 3, 1),
        citation_count=8,
        hn_points=200,
        full_text="(full text would go here)",
    ),
    Paper(
        arxiv_id="2403.19912",
        title="Constitutional AI Without Human Feedback",
        abstract="We show that language models can self-improve safety without human feedback by generating and critiquing their own outputs using constitutional principles.",
        authors=[Author(name="James Park", affiliation="Anthropic Research")],
        categories=["cs.AI", "cs.CL"],
        published_date=datetime(2025, 3, 1),
        citation_count=20,
        hn_points=150,
        full_text="(full text would go here)",
    ),
    Paper(
        arxiv_id="2403.19923",
        title="Sparse Mixture of LoRAs for Multi-Task Learning",
        abstract="We combine mixture-of-experts routing with LoRA adapters, enabling a single base model to serve 100+ tasks with only 2% parameter overhead per task.",
        authors=[Author(name="Yuki Tanaka", affiliation="Google Research")],
        categories=["cs.LG"],
        published_date=datetime(2025, 3, 1),
        citation_count=4,
        full_text="(full text would go here)",
    ),
    Paper(
        arxiv_id="2403.19934",
        title="Detecting Machine-Generated Scientific Text",
        abstract="A classifier that detects LLM-generated text in scientific papers with 94% accuracy, robust to paraphrasing attacks.",
        authors=[Author(name="Maria Garcia", affiliation="MIT CSAIL")],
        categories=["cs.CL", "cs.CR"],
        published_date=datetime(2025, 3, 1),
        citation_count=2,
        full_text="(full text would go here)",
    ),
]

ANCHOR = AnchorDocument(
    week="2025-W10",
    updated_by="Paula",
    updated_at=datetime.utcnow(),
    hot_topics=[
        "reasoning in language models",
        "reinforcement learning for LLMs",
        "efficient inference and serving",
        "AI safety and alignment",
    ],
    declining_topics=["GANs", "word2vec", "BERT fine-tuning"],
    boost_keywords=["reasoning", "reinforcement learning", "scaling", "inference", "safety"],
    institutions_of_interest=["Stanford", "DeepMind", "Anthropic", "Google", "Meta"],
)


# Mock LLM response for content generation
MOCK_GENERATED_PIECE = """{
    "title": "Teaching Machines to Reason Through Trial and Error",
    "hook": "A 7-billion parameter model with a learned reasoning strategy matches a 70-billion parameter model using standard prompting — by treating thinking as a skill to practice, not a pattern to copy.",
    "content": "## The Problem\\nLarge language models can do a lot, but multi-step reasoning trips them up [§1]. Chain-of-thought prompting — showing a model examples of step-by-step thinking — helps, but it depends on having good examples and doesn't learn from mistakes. ReasonAgent takes a different approach: what if we treated reasoning itself as a skill that could be practiced and improved through reinforcement learning [Abstract]?\\n\\n## What They Did\\nThe team at Stanford and DeepMind built a lightweight reasoning controller (45 million parameters) that sits on top of a frozen language model [§2.1]. Instead of generating text directly, this controller learns four actions: DECOMPOSE a problem into parts, SOLVE individual steps, VERIFY intermediate results, and BACKTRACK when something goes wrong.\\n\\nThey trained this controller using PPO (a standard reinforcement learning algorithm) on 50,000 problems spanning arithmetic, algebra, geometry, and logic [§2.2]. The signal is simple: did you get the right answer or not? A KL penalty keeps the reasoning policy from straying too far from how the base model naturally thinks.\\n\\n## The Results\\nOn GSM8K (a standard math reasoning benchmark), ReasonAgent hit 89.2% accuracy compared to 78.1% for chain-of-thought prompting and 64.3% for standard prompting [Table 1]. The gains were consistent across benchmarks: 71.4% on ARC-Challenge, 47.8% on MATH, and 68.9% on LogiQA [§3].\\n\\nTwo findings stand out. First, a reasoning policy trained only on math problems transfers to logical reasoning with just 12% degradation — 63.1% on ARC-Challenge versus 71.4% with direct training [§3.1]. The model learned something general about how to think, not just math-specific tricks.\\n\\nSecond, a 7B parameter model using ReasonAgent (89.2% on GSM8K) matched a 70B model with standard prompting (88.7%) [§3.2]. Learned reasoning strategies appear to compensate for raw model size [Figure 2].\\n\\nThe approach has limits. Training requires about 200 GPU-hours on A100s for the 7B model [§4]. It also struggles with problems needing more than 15 reasoning steps, where the policy tends to loop rather than make progress [§4].\\n\\n## Why It Matters\\nFor practitioners, this suggests a concrete alternative to prompt engineering for reasoning tasks. Rather than crafting better examples, you can train a small adapter that teaches a model how to think through problems. The transfer results are particularly interesting — they hint that reasoning might be a learnable, general capability rather than something domain-specific.",
    "sections": ["The Problem", "What They Did", "The Results", "Why It Matters"]
}"""

MOCK_VERIFICATION_RESPONSE = """{
    "claims_checked": 12,
    "claims_verified": 11,
    "claims_failed": 1,
    "issues": [{
        "severity": "minor",
        "type": "missing_context",
        "claim_text": "a 7B parameter model using ReasonAgent (89.2% on GSM8K) matched a 70B model with standard prompting (88.7%)",
        "cited_passage": "A 7B model with ReasonAgent (89.2% on GSM8K) matches a 70B model using standard prompting (88.7%)",
        "explanation": "The claim accurately represents the numbers but omits that the 70B comparison is for 'standard prompting' specifically, not CoT. The 70B model with CoT likely performs better.",
        "suggested_fix": null
    }],
    "overall_assessment": "Well-grounded piece. Numbers are accurate. One minor omission about the comparison conditions for model size results."
}"""


# ── Helpers ──────────────────────────────────────────────────────────

def hr(title=""):
    width = 70
    if title:
        print(f"\n{'─' * 3} {title} {'─' * (width - len(title) - 5)}")
    else:
        print(f"{'─' * width}")


def wrap(text, indent=2):
    return textwrap.fill(text, width=68, initial_indent=" " * indent, subsequent_indent=" " * indent)


# ── Pipeline stages ─────────────────────────────────────────────────

async def demo():
    all_papers = [SAMPLE_PAPER] + OTHER_PAPERS

    # ━━ STAGE 1: SCORING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("STAGE 1: SCORING")
    print(f"\n  Scoring {len(all_papers)} papers against anchor for week {ANCHOR.week}")
    print(f"  Hot topics: {', '.join(ANCHOR.hot_topics)}")
    print(f"  Boost keywords: {', '.join(ANCHOR.boost_keywords)}")

    # Score relevance (no LLM needed)
    from signal.curate.models import ScoredPaper
    scored_papers = []
    for paper in all_papers:
        rel = await score_relevance(paper, ANCHOR)
        # Use heuristic for narrative (no LLM in demo)
        from signal.curate.score import _heuristic_narrative_score
        nar = _heuristic_narrative_score(paper)
        composite = (rel + nar) / 2
        sp = ScoredPaper(
            paper=paper,
            relevance_score=round(rel, 2),
            narrative_potential_score=round(nar, 2),
            composite_score=round(composite, 2),
        )
        scored_papers.append(sp)

    scored_papers.sort(key=lambda x: x.composite_score, reverse=True)

    print(f"\n  {'Paper':<55} {'Rel':>5} {'Nar':>5} {'Comp':>5}")
    print(f"  {'─' * 55} {'─' * 5} {'─' * 5} {'─' * 5}")
    for sp in scored_papers:
        title = sp.paper.title[:53]
        print(f"  {title:<55} {sp.relevance_score:5.1f} {sp.narrative_potential_score:5.1f} {sp.composite_score:5.1f}")

    # ━━ STAGE 2: SELECTION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("STAGE 2: SELECTION")

    config = SelectionConfig(target_count=3, min_count=2)
    selected = select_edition_papers(scored_papers, config)
    runners_up = get_runners_up(scored_papers, selected, count=3)

    print(f"\n  Selected {len(selected)} papers for edition:")
    for sp in selected:
        print(f"    ✓ [{sp.paper.arxiv_id}] {sp.paper.title[:60]}")
        print(f"      Score: {sp.composite_score:.1f} | {sp.selection_reason}")

    print(f"\n  Runners-up ({len(runners_up)}):")
    for sp in runners_up:
        print(f"    ○ [{sp.paper.arxiv_id}] {sp.paper.title[:60]}")

    # ━━ STAGE 3: CONTENT GENERATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("STAGE 3: CONTENT GENERATION")
    print(f"\n  Generating piece for: {SAMPLE_PAPER.title}")

    with patch("signal.generate.writer._generate_with_anthropic", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_GENERATED_PIECE
        piece = await generate_piece(SAMPLE_PAPER, GenerationConfig(llm_provider="anthropic"))

    print(f"\n  Title: {piece.title}")
    print(f"  Hook: {piece.hook}")
    print(f"  Words: {piece.word_count}")
    print(f"  Citations: {len(piece.citations)}")

    print(f"\n  Citation references found:")
    for cit in piece.citations[:8]:
        claim_preview = cit['claim'][:50] + "..." if len(cit['claim']) > 50 else cit['claim']
        print(f"    [{cit['citation']}] {claim_preview}")
    if len(piece.citations) > 8:
        print(f"    ... and {len(piece.citations) - 8} more")

    print(f"\n  --- Generated Content (first 800 chars) ---")
    content_preview = piece.content[:800]
    for line in content_preview.split("\n"):
        print(f"  {line}")
    print(f"  ...")

    # ━━ STAGE 4: VERIFICATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("STAGE 4: VERIFICATION")

    with patch("signal.verify.checker._verify_with_anthropic", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = MOCK_VERIFICATION_RESPONSE
        report = await verify_piece(piece, SAMPLE_PAPER, VerificationConfig(llm_provider="anthropic"))

    print(f"\n  Status: {report.status.upper()}")
    print(f"  Claims checked: {report.claims_checked}")
    print(f"  Claims verified: {report.claims_verified}")
    print(f"  Claims failed: {report.claims_failed}")
    print(f"  Pass rate: {report.pass_rate:.0%}")

    if report.issues:
        print(f"\n  Issues ({len(report.issues)}):")
        for issue in report.issues:
            print(f"    [{issue.severity.value}] {issue.issue_type.value}")
            print(f"      Claim: {issue.claim_text[:70]}")
            print(f"      Explanation: {issue.explanation[:70]}")

    # ━━ STAGE 5: STYLE CHECK ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("STAGE 5: STYLE CHECK")

    style_report = await check_style_compliance(piece, StyleConfig(min_words=100, max_words=2000))

    print(f"\n  Compliant: {'YES' if style_report.compliant else 'NO'}")
    print(f"  Word count: {style_report.word_count} (target: 100-2000)")

    if style_report.issues:
        print(f"\n  Style issues ({len(style_report.issues)}):")
        for issue in style_report.issues:
            print(f"    [{issue.severity}] {issue.issue_type}: {issue.description}")
    else:
        print(f"  No style issues found.")

    # ━━ STAGE 6: EDITION ASSEMBLY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("STAGE 6: EDITION ASSEMBLY")

    piece.verified = True

    from signal.generate.edition import QuickTake
    with patch("signal.generate.edition.generate_quick_take", new_callable=AsyncMock) as mock_qt:
        mock_qt.side_effect = [
            QuickTake(
                paper_id=sp.paper.arxiv_id,
                title=sp.paper.title,
                one_liner=sp.paper.abstract.split(". ")[0] + ".",
                paper_url=f"https://arxiv.org/abs/{sp.paper.arxiv_id}",
            )
            for sp in runners_up
        ]
        edition = await assemble_edition(
            [piece], runners_up, "2025-W10", 42,
            AssemblyConfig(max_pieces=3, max_quick_takes=3),
        )

    subject = generate_edition_subject(edition)

    print(f"\n  Edition: {edition.week} (Issue #{edition.issue_number})")
    print(f"  Subject: {subject}")
    print(f"  Pieces: {len(edition.pieces)}")
    print(f"  Quick Takes: {len(edition.quick_takes)}")
    print(f"  Total words: {edition.total_words}")

    if edition.quick_takes:
        print(f"\n  Quick Takes:")
        for qt in edition.quick_takes:
            print(f"    • {qt.title[:55]}")
            print(f"      {qt.one_liner[:65]}")

    # ━━ STAGE 7: PUBLISHING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("STAGE 7: PUBLISHING")

    html = render_edition_html(edition)
    text = render_edition_text(edition)

    print(f"\n  HTML email: {len(html)} chars")
    print(f"  Plain text: {len(text)} chars")

    # Write outputs
    out = Path("data/demo_output")
    out.mkdir(parents=True, exist_ok=True)

    (out / "edition.html").write_text(html)
    (out / "edition.txt").write_text(text)

    # Web page
    web_html = generate_edition_page(edition, WebConfig(site_url="https://signal.example.com"))
    (out / "web_page.html").write_text(web_html)

    # RSS
    rss = generate_rss_feed([edition], WebConfig(site_url="https://signal.example.com"))
    (out / "rss.xml").write_text(rss)

    print(f"\n  Output written to {out}/:")
    print(f"    edition.html  — Email HTML version")
    print(f"    edition.txt   — Email plain text version")
    print(f"    web_page.html — Web archive page")
    print(f"    rss.xml       — RSS feed")

    # ━━ PLAIN TEXT PREVIEW ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    hr("PLAIN TEXT EMAIL PREVIEW")
    # Show first ~40 lines of the plain text version
    lines = text.split("\n")
    for line in lines[:45]:
        print(f"  {line}")
    if len(lines) > 45:
        print(f"  ... ({len(lines) - 45} more lines)")

    hr()
    print(f"\n  Pipeline complete. {len(all_papers)} papers → 1 edition → 4 output files\n")


if __name__ == "__main__":
    loop.run_until_complete(demo())
    loop.close()
