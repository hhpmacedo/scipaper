"""
Tests for the PDF parser module.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import run_async

from signal.generate.pdf_parser import (
    ParsedPaper,
    ParserConfig,
    PyMuPDFParser,
    download_paper_pdf,
    parse_paper_pdf,
)


class TestPyMuPDFParser:
    def test_extract_title(self):
        parser = PyMuPDFParser()
        first_page = "A Novel Method for Large Language Models\n\nAlice Smith, Bob Jones\n\nAbstract"
        title = parser._extract_title(first_page)
        assert "Novel Method" in title

    def test_extract_title_skips_arxiv_header(self):
        parser = PyMuPDFParser()
        first_page = "arXiv:2403.12345v1 [cs.AI]\nPreprint\nActual Title Here\nAuthors"
        title = parser._extract_title(first_page)
        assert "Actual Title Here" in title

    def test_extract_abstract(self):
        parser = PyMuPDFParser()
        text = """Abstract
This paper presents a novel approach to reasoning in large language models.
We demonstrate improved performance on mathematical benchmarks.

1 Introduction
Language models have shown remarkable progress..."""
        abstract = parser._extract_abstract(text)
        assert "novel approach" in abstract

    def test_extract_sections(self):
        parser = PyMuPDFParser()
        text = """1 Introduction
This is the introduction text.
Some more text here.

2 Methods
We use the following method.

2.1 Data Collection
We collected data from various sources.

3 Results
Our results show improvement."""
        sections = parser._extract_sections(text)
        assert len(sections) >= 3
        assert sections[0]["number"] == "1"
        assert sections[0]["title"] == "Introduction"

    def test_section_pattern(self):
        pattern = PyMuPDFParser.SECTION_PATTERN
        assert pattern.search("1 Introduction")
        assert pattern.search("2.1 Data Collection")
        assert pattern.search("3 Results and Discussion")
        assert not pattern.search("some random text")


class TestParseChain:
    def test_fallback_chain(self):
        config = ParserConfig(parsers=["pymupdf", "llm"])

        mock_parsed = ParsedPaper(
            arxiv_id="test",
            title="Test",
            abstract="Abstract",
            sections=[],
            full_text="Full text content",
            parser_used="llm_fallback_raw",
            parse_quality="fallback",
        )

        with patch.object(PyMuPDFParser, "parse", return_value=None):
            with patch(
                "signal.generate.pdf_parser.LLMParser.parse",
                return_value=mock_parsed,
            ):
                result = run_async(
                    parse_paper_pdf(Path("/tmp/test.pdf"), "test-id", config)
                )

        assert result.parser_used == "llm_fallback_raw"

    def test_all_parsers_fail(self):
        config = ParserConfig(parsers=["pymupdf"])

        with patch.object(PyMuPDFParser, "parse", return_value=None):
            with pytest.raises(ValueError, match="All parsers failed"):
                run_async(
                    parse_paper_pdf(Path("/tmp/test.pdf"), "test-id", config)
                )


class TestDownloadPaperPdf:
    def test_download_success(self, tmp_path):
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 fake content"
        mock_response.raise_for_status = MagicMock()

        with patch("signal.generate.pdf_parser.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            path = run_async(download_paper_pdf("2403.12345", tmp_path))

        assert path.exists()
        assert path.read_bytes() == b"%PDF-1.4 fake content"

    def test_download_cached(self, tmp_path):
        cached = tmp_path / "2403.12345.pdf"
        cached.write_bytes(b"cached content")

        path = run_async(download_paper_pdf("2403.12345", tmp_path))
        assert path == cached
        assert path.read_bytes() == b"cached content"
