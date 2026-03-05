"""
Tests for the content generation module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import run_async

from scipaper.generate.writer import (
    GenerationConfig,
    Piece,
    extract_citations,
    generate_piece,
    validate_citations,
    _parse_generation_response,
)
from scipaper.curate.models import Author, Paper


def make_paper(**kwargs):
    defaults = dict(
        arxiv_id="2403.12345",
        title="Test Paper",
        abstract="A test abstract.",
        authors=[Author(name="Alice")],
        categories=["cs.AI"],
        full_text="Abstract\nTest abstract.\n\n1 Introduction\nThis is the intro.\n\n2 Methods\nOur method.\n\n2.1 Data\nData details.\n\n3 Results\nResults here.\n\nTable 1: Results.\nFigure 1: Overview.",
    )
    defaults.update(kwargs)
    return Paper(**defaults)


class TestExtractCitations:
    def test_section_citations(self):
        content = "The model achieves 90% accuracy [§3.2] on the benchmark."
        cits = extract_citations(content)
        assert len(cits) == 1
        assert cits[0]["citation"] == "§3.2"

    def test_abstract_citation(self):
        content = "This paper introduces a new method [Abstract] for reasoning."
        cits = extract_citations(content)
        assert len(cits) == 1
        assert cits[0]["citation"] == "Abstract"

    def test_table_citation(self):
        content = "Results are shown in detail [Table 1] and demonstrate gains."
        cits = extract_citations(content)
        assert len(cits) == 1
        assert cits[0]["citation"] == "Table 1"

    def test_figure_citation(self):
        content = "The architecture is depicted [Figure 3] in the paper."
        cits = extract_citations(content)
        assert len(cits) == 1
        assert cits[0]["citation"] == "Figure 3"

    def test_multiple_citations(self):
        content = (
            "The model works well [§2.1] and results confirm [Table 1] improvements. "
            "As noted [Abstract] this is important."
        )
        cits = extract_citations(content)
        assert len(cits) == 3

    def test_no_citations(self):
        content = "This text has no citations at all."
        assert extract_citations(content) == []


class TestValidateCitations:
    def test_valid_section(self):
        paper_text = "1 Introduction\nText.\n\n2.1 Methods\nMore text."
        cits = [{"claim": "test", "citation": "§2.1"}]
        invalid = validate_citations(cits, paper_text)
        assert invalid == []

    def test_invalid_section(self):
        paper_text = "1 Introduction\nText."
        cits = [{"claim": "test", "citation": "§9.9"}]
        invalid = validate_citations(cits, paper_text)
        assert len(invalid) == 1

    def test_abstract_always_valid(self):
        cits = [{"claim": "test", "citation": "Abstract"}]
        invalid = validate_citations(cits, "Any text")
        assert invalid == []

    def test_valid_table(self):
        paper_text = "Table 1: Results showing improvements."
        cits = [{"claim": "test", "citation": "Table 1"}]
        assert validate_citations(cits, paper_text) == []

    def test_invalid_table(self):
        paper_text = "No tables here."
        cits = [{"claim": "test", "citation": "Table 5"}]
        assert len(validate_citations(cits, paper_text)) == 1


class TestParseGenerationResponse:
    def test_parses_json(self):
        resp = '{"title": "Test", "hook": "Hook", "content": "Body text"}'
        result = _parse_generation_response(resp)
        assert result["title"] == "Test"
        assert result["content"] == "Body text"

    def test_parses_json_in_code_block(self):
        resp = '```json\n{"title": "Test", "hook": "H", "content": "C"}\n```'
        result = _parse_generation_response(resp)
        assert result["title"] == "Test"

    def test_fallback_plain_text(self):
        resp = "This is just plain text. With multiple sentences."
        result = _parse_generation_response(resp)
        assert result["content"] == resp
        assert "plain text." in result["hook"]


class TestGeneratePiece:
    def test_requires_full_text(self):
        paper = make_paper(full_text=None)
        with pytest.raises(ValueError, match="no full text"):
            run_async(generate_piece(paper))

    def test_generate_with_anthropic(self):
        paper = make_paper()

        with patch("scipaper.generate.writer._generate_with_anthropic", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = '{"title": "Test Piece", "hook": "A hook.", "content": "Body [§1] text [Abstract]."}'
            piece = run_async(generate_piece(paper, GenerationConfig(llm_provider="anthropic")))

        assert piece.paper_id == "2403.12345"
        assert piece.title == "Test Piece"
        assert len(piece.citations) >= 1

    def test_generate_with_openai(self):
        paper = make_paper()

        with patch("scipaper.generate.writer._generate_with_openai", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = '{"title": "OAI Piece", "hook": "Hook.", "content": "Text [§2.1]."}'
            piece = run_async(generate_piece(paper, GenerationConfig(llm_provider="openai")))

        assert piece.title == "OAI Piece"
