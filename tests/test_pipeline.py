"""
End-to-end integration test for the full Signal pipeline.

Mocks external services (ArXiv, LLM APIs) but wires together
all internal pipeline stages to verify the complete flow:
  Ingest → Score → Select → Generate → Verify → Style → Publish
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from .conftest import run_async

from signal.curate.models import AnchorDocument, Author, Paper
from signal.generate.writer import Piece
from signal.pipeline import PipelineConfig, run_pipeline
from signal.curate.score import ScoringConfig
from signal.curate.select import SelectionConfig
from signal.generate.writer import GenerationConfig
from signal.generate.edition import AssemblyConfig
from signal.verify.checker import VerificationConfig
from signal.verify.style import StyleConfig
from signal.publish.web import WebConfig


# ── Fixtures ─────────────────────────────────────────────────────────


SAMPLE_FULL_TEXT = """Abstract
We present a method for improving reasoning in large language models through
structured chain-of-thought prompting. Our approach achieves 42% improvement
on the GSM8K benchmark.

1 Introduction
Large language models have shown remarkable capabilities in natural language
tasks. However, complex reasoning remains challenging.

2 Methods
We propose structured chain-of-thought (SCoT) prompting which decomposes
complex problems into sub-problems.

2.1 Data Collection
We collected 10,000 reasoning problems from diverse mathematical domains.

3 Results
Our method achieves 85.3% accuracy on GSM8K, compared to 60.1% for standard
prompting. Table 1 shows detailed results. Figure 1 illustrates the improvement.

Table 1: Results on GSM8K benchmark.
Figure 1: Accuracy comparison across methods.

4 Limitations
Our approach requires more compute at inference time. Performance on
non-mathematical reasoning tasks is less clear.

5 Conclusion
Structured chain-of-thought prompting offers substantial improvements for
mathematical reasoning in LLMs.
"""


def make_sample_papers():
    """Create realistic sample papers with full text."""
    return [
        Paper(
            arxiv_id="2403.10001",
            title="Structured Chain-of-Thought Prompting for Mathematical Reasoning",
            abstract="We present a method for improving reasoning in LLMs through structured prompting. 42% improvement on GSM8K.",
            authors=[
                Author(name="Alice Smith", affiliation="Stanford CS"),
                Author(name="Bob Jones", affiliation="DeepMind"),
            ],
            categories=["cs.AI", "cs.CL"],
            published_date=datetime.utcnow(),
            pdf_url="https://arxiv.org/pdf/2403.10001",
            citation_count=15,
            hn_points=50,
            full_text=SAMPLE_FULL_TEXT,
        ),
        Paper(
            arxiv_id="2403.10002",
            title="Efficient Fine-Tuning of Vision Transformers with Adapter Layers",
            abstract="We propose lightweight adapter layers for vision transformers that reduce fine-tuning costs by 90%.",
            authors=[
                Author(name="Carol Lee", affiliation="Google Research"),
            ],
            categories=["cs.LG", "cs.CV"],
            published_date=datetime.utcnow(),
            pdf_url="https://arxiv.org/pdf/2403.10002",
            citation_count=8,
            full_text=SAMPLE_FULL_TEXT.replace("chain-of-thought", "adapter").replace("GSM8K", "ImageNet"),
        ),
        Paper(
            arxiv_id="2403.10003",
            title="Scaling Laws for Mixture-of-Experts Language Models",
            abstract="We study scaling behavior of MoE models, finding sub-linear compute scaling with expert count.",
            authors=[
                Author(name="Dave Park", affiliation="Anthropic Research"),
            ],
            categories=["cs.AI", "stat.ML"],
            published_date=datetime.utcnow(),
            citation_count=25,
            hn_points=120,
            full_text=SAMPLE_FULL_TEXT.replace("chain-of-thought", "mixture-of-experts").replace("GSM8K", "MMLU"),
        ),
        Paper(
            arxiv_id="2403.10004",
            title="Watermarking Neural Network Outputs for IP Protection",
            abstract="A watermarking scheme for LLM outputs that is robust to paraphrasing attacks.",
            authors=[
                Author(name="Eve Wang", affiliation="MIT CSAIL"),
            ],
            categories=["cs.CR", "cs.AI"],
            published_date=datetime.utcnow(),
            citation_count=3,
            full_text=SAMPLE_FULL_TEXT.replace("chain-of-thought", "watermarking").replace("GSM8K", "detection"),
        ),
        Paper(
            arxiv_id="2403.10005",
            title="Low-Rank Approximations for Efficient Inference",
            abstract="We compress transformer attention matrices using low-rank factorization, achieving 3x speedup.",
            authors=[
                Author(name="Frank Chen", affiliation="Meta AI"),
            ],
            categories=["cs.LG"],
            published_date=datetime.utcnow(),
            citation_count=5,
            full_text=SAMPLE_FULL_TEXT.replace("chain-of-thought", "low-rank").replace("GSM8K", "WikiText"),
        ),
    ]


def make_anchor():
    return AnchorDocument(
        week="2025-W10",
        updated_by="test",
        updated_at=datetime.utcnow(),
        hot_topics=[
            "chain-of-thought reasoning",
            "scaling laws",
            "efficient fine-tuning",
        ],
        declining_topics=["GANs", "word embeddings"],
        boost_keywords=["reasoning", "scaling", "efficiency", "prompting"],
        institutions_of_interest=["Stanford", "DeepMind", "Anthropic", "Google"],
    )


# LLM response mocks
MOCK_GENERATION_RESPONSE = """{
    "title": "Teaching LLMs to Think Step by Step",
    "hook": "A new prompting technique doubles mathematical reasoning accuracy by forcing models to show their work.",
    "content": "## The Problem\\nLarge language models struggle with multi-step mathematical reasoning [Abstract]. While they can handle simple arithmetic, problems requiring chains of logic often trip them up [§1].\\n\\n## What They Did\\nResearchers at Stanford and DeepMind developed structured chain-of-thought (SCoT) prompting [§2], which breaks complex problems into explicit sub-problems [§2.1]. Rather than asking a model to solve a problem in one shot, SCoT forces intermediate steps.\\n\\n## The Results\\nOn the GSM8K math benchmark, SCoT achieved 85.3% accuracy versus 60.1% for standard prompting [§3] — a 42% relative improvement [Abstract]. Table 1 shows consistent gains across problem types [Table 1]. Figure 1 illustrates the accuracy gap [Figure 1].\\n\\n## Why It Matters\\nFor engineers using LLMs in production, this suggests that prompt engineering for reasoning tasks should prioritize structure over cleverness. The 42% improvement comes with a trade-off: more compute at inference time [§4].",
    "sections": ["The Problem", "What They Did", "The Results", "Why It Matters"]
}"""


MOCK_VERIFICATION_RESPONSE = """{
    "claims_checked": 8,
    "claims_verified": 7,
    "claims_failed": 1,
    "issues": [{
        "severity": "minor",
        "type": "missing_context",
        "claim_text": "doubles mathematical reasoning accuracy",
        "cited_passage": "42% relative improvement",
        "explanation": "Hook says 'doubles' but the actual improvement is 42%, not 100%",
        "suggested_fix": "significantly improves mathematical reasoning accuracy"
    }],
    "overall_assessment": "Mostly accurate with one minor overstatement in the hook."
}"""

MOCK_QUICK_TAKE_RESPONSE = "Lightweight adapters cut vision transformer fine-tuning costs by 90% while maintaining accuracy."


# ── Tests ────────────────────────────────────────────────────────────


class TestEndToEndPipeline:
    """Full pipeline integration tests."""

    def _make_config(self, tmp_path):
        return PipelineConfig(
            scoring=ScoringConfig(llm_provider="anthropic"),
            selection=SelectionConfig(target_count=3, min_count=2),
            generation=GenerationConfig(llm_provider="anthropic"),
            verification=VerificationConfig(llm_provider="anthropic"),
            style=StyleConfig(min_words=50, max_words=5000),
            assembly=AssemblyConfig(max_pieces=3, max_quick_takes=2),
            web=WebConfig(output_dir=tmp_path / "public"),
            week="2025-W10",
            issue_number=42,
            skip_pdf_download=True,
        )

    def test_full_pipeline_produces_edition(self, tmp_path):
        """End-to-end: papers in → edition out with web archive."""
        papers = make_sample_papers()
        anchor = make_anchor()
        config = self._make_config(tmp_path)

        with (
            patch("signal.curate.score._score_with_anthropic", new_callable=AsyncMock) as mock_narrative,
            patch("signal.generate.writer._generate_with_anthropic", new_callable=AsyncMock) as mock_gen,
            patch("signal.verify.checker._verify_with_anthropic", new_callable=AsyncMock) as mock_verify,
            patch("signal.generate.edition.generate_quick_take", new_callable=AsyncMock) as mock_qt,
        ):
            # Narrative scoring: _score_with_anthropic returns a float
            mock_narrative.return_value = 7.0
            # Content generation
            mock_gen.return_value = MOCK_GENERATION_RESPONSE
            # Verification
            mock_verify.return_value = MOCK_VERIFICATION_RESPONSE
            # Quick takes
            from signal.generate.edition import QuickTake
            mock_qt.return_value = QuickTake(
                paper_id="runner",
                title="Runner-Up Paper",
                one_liner=MOCK_QUICK_TAKE_RESPONSE,
                paper_url="https://arxiv.org/abs/runner",
            )

            result = run_async(run_pipeline(anchor, config, papers=papers))

        # Verify pipeline ran through all stages
        assert result.papers_ingested == 5
        assert result.papers_scored == 5
        assert result.papers_selected >= 2
        assert result.pieces_generated >= 1
        assert result.pieces_verified >= 1
        assert result.pieces_passed >= 1

        # Verify edition was produced
        assert result.edition is not None
        assert result.edition.week == "2025-W10"
        assert result.edition.issue_number == 42
        assert len(result.edition.pieces) >= 1
        assert result.edition.total_words > 0

        # Verify each piece has citations and verification
        for piece in result.edition.pieces:
            assert piece.verified is True
            assert piece.verification_report is not None
            assert piece.word_count > 0

        # Verify web archive was generated
        assert result.web_output is not None
        assert (result.web_output / "index.html").exists()
        assert (result.web_output / "editions" / "2025-W10.html").exists()
        assert (result.web_output / "rss.xml").exists()
        assert (result.web_output / "feed.json").exists()

        # Check web content is sensible
        index = (result.web_output / "index.html").read_text()
        assert "Signal" in index
        assert "#42" in index

        edition_page = (result.web_output / "editions" / "2025-W10.html").read_text()
        assert "Teaching LLMs" in edition_page or "Step by Step" in edition_page

    def test_pipeline_with_no_papers(self):
        """Pipeline handles empty input gracefully."""
        anchor = make_anchor()
        config = PipelineConfig(week="2025-W10", skip_pdf_download=True)

        with patch("signal.curate.score._score_with_anthropic", new_callable=AsyncMock) as mock:
            mock.return_value = 5.0
            result = run_async(run_pipeline(anchor, config, papers=[]))

        assert result.papers_ingested == 0
        assert result.edition is None
        assert result.errors == []

    def test_pipeline_survives_generation_failure(self, tmp_path):
        """Pipeline continues when one piece fails to generate."""
        papers = make_sample_papers()[:3]
        anchor = make_anchor()
        config = self._make_config(tmp_path)
        config.selection = SelectionConfig(target_count=3, min_count=2)

        call_count = 0

        async def flaky_generate(prompt, gen_config):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Simulated LLM failure")
            return MOCK_GENERATION_RESPONSE

        with (
            patch("signal.curate.score._score_with_anthropic", new_callable=AsyncMock) as mock_narrative,
            patch("signal.generate.writer._generate_with_anthropic", new=flaky_generate),
            patch("signal.verify.checker._verify_with_anthropic", new_callable=AsyncMock) as mock_verify,
            patch("signal.generate.edition.generate_quick_take", new_callable=AsyncMock) as mock_qt,
        ):
            mock_narrative.return_value = 7.0
            mock_verify.return_value = MOCK_VERIFICATION_RESPONSE
            from signal.generate.edition import QuickTake
            mock_qt.return_value = QuickTake(
                paper_id="r", title="R", one_liner="Summary.", paper_url="https://arxiv.org"
            )

            result = run_async(run_pipeline(anchor, config, papers=papers))

        # One generation failed, but pipeline continued
        assert len(result.errors) >= 1
        assert "Simulated LLM failure" in result.errors[0]
        # Should still have produced some pieces
        assert result.pieces_generated >= 1

    def test_pipeline_rejects_bad_verification(self, tmp_path):
        """Pieces with critical verification issues are rejected."""
        papers = make_sample_papers()[:2]
        anchor = make_anchor()
        config = self._make_config(tmp_path)
        config.selection = SelectionConfig(target_count=2, min_count=1)

        critical_response = """{
            "claims_checked": 5,
            "claims_verified": 1,
            "claims_failed": 4,
            "issues": [{
                "severity": "critical",
                "type": "misrepresented",
                "claim_text": "doubles accuracy",
                "cited_passage": "modest 5% improvement",
                "explanation": "Completely misrepresents the finding"
            }]
        }"""

        with (
            patch("signal.curate.score._score_with_anthropic", new_callable=AsyncMock) as mock_narrative,
            patch("signal.generate.writer._generate_with_anthropic", new_callable=AsyncMock) as mock_gen,
            patch("signal.verify.checker._verify_with_anthropic", new_callable=AsyncMock) as mock_verify,
        ):
            mock_narrative.return_value = 7.0
            mock_gen.return_value = MOCK_GENERATION_RESPONSE
            mock_verify.return_value = critical_response

            result = run_async(run_pipeline(anchor, config, papers=papers))

        # All pieces should be rejected (critical issue)
        assert result.pieces_passed == 0
        assert result.edition is None

    def test_pipeline_stats_are_consistent(self, tmp_path):
        """Pipeline result stats form a monotonically decreasing funnel."""
        papers = make_sample_papers()
        anchor = make_anchor()
        config = self._make_config(tmp_path)

        with (
            patch("signal.curate.score._score_with_anthropic", new_callable=AsyncMock) as mock_narrative,
            patch("signal.generate.writer._generate_with_anthropic", new_callable=AsyncMock) as mock_gen,
            patch("signal.verify.checker._verify_with_anthropic", new_callable=AsyncMock) as mock_verify,
            patch("signal.generate.edition.generate_quick_take", new_callable=AsyncMock) as mock_qt,
        ):
            mock_narrative.return_value = 7.0
            mock_gen.return_value = MOCK_GENERATION_RESPONSE
            mock_verify.return_value = MOCK_VERIFICATION_RESPONSE
            from signal.generate.edition import QuickTake
            mock_qt.return_value = QuickTake(
                paper_id="r", title="R", one_liner="S.", paper_url="https://arxiv.org"
            )

            result = run_async(run_pipeline(anchor, config, papers=papers))

        # Funnel: ingested >= scored >= selected >= generated >= verified >= passed
        assert result.papers_ingested >= result.papers_scored
        assert result.papers_scored >= result.papers_selected
        assert result.papers_selected >= result.pieces_generated
        assert result.pieces_generated >= result.pieces_verified
        assert result.pieces_verified >= result.pieces_passed
