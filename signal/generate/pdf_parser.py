"""
PDF parsing for academic papers.

Attempts multiple strategies to extract structured text from paper PDFs.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ParsedPaper:
    """Structured content extracted from a paper PDF."""
    arxiv_id: str
    title: str
    abstract: str

    # Structured sections
    sections: List[dict]  # {number: "1.2", title: "Methods", content: "..."}

    # Raw full text (fallback)
    full_text: str

    # Extraction metadata
    parser_used: str
    parse_quality: str  # "good", "partial", "fallback"


@dataclass
class ParserConfig:
    """Configuration for PDF parsing."""
    # Parser priority
    parsers: List[str] = None  # ["pymupdf", "grobid", "llm"]

    # GROBID settings (if available)
    grobid_url: Optional[str] = None

    # LLM fallback settings
    llm_model: str = "claude-sonnet-4-20250514"

    def __post_init__(self):
        if self.parsers is None:
            self.parsers = ["pymupdf", "grobid", "llm"]


class PyMuPDFParser:
    """
    Fast PDF text extraction using PyMuPDF (fitz).

    Good for simple layouts, struggles with complex academic formatting.
    """

    # Patterns for detecting section headers
    SECTION_PATTERN = re.compile(
        r'^(\d+(?:\.\d+)*)\s+([A-Z][^\n]{2,80})$', re.MULTILINE
    )

    def parse(self, pdf_path: Path, arxiv_id: str = "") -> Optional[ParsedPaper]:
        """
        Extract text from PDF using PyMuPDF.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF not installed (pip install pymupdf)")
            return None

        logger.info(f"Parsing {pdf_path} with PyMuPDF")

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.warning(f"Failed to open PDF {pdf_path}: {e}")
            return None

        # Extract text from all pages
        pages_text = []
        for page in doc:
            text = page.get_text("text")
            if text:
                pages_text.append(text)

        doc.close()

        if not pages_text:
            logger.warning(f"No text extracted from {pdf_path}")
            return None

        full_text = "\n\n".join(pages_text)

        # Extract title (usually first large text on page 1)
        title = self._extract_title(pages_text[0]) if pages_text else arxiv_id

        # Extract abstract
        abstract = self._extract_abstract(full_text)

        # Extract sections
        sections = self._extract_sections(full_text)

        # Assess quality
        quality = "good"
        if len(sections) < 3:
            quality = "partial"
        if len(full_text) < 1000:
            quality = "fallback"

        return ParsedPaper(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            sections=sections,
            full_text=full_text,
            parser_used="pymupdf",
            parse_quality=quality,
        )

    def _extract_title(self, first_page: str) -> str:
        """Extract title from first page text."""
        lines = first_page.strip().split("\n")
        # Title is typically one of the first non-empty lines
        title_lines = []
        for line in lines[:10]:
            line = line.strip()
            if not line:
                if title_lines:
                    break
                continue
            # Skip common header elements
            if any(
                kw in line.lower()
                for kw in ["arxiv:", "preprint", "published", "under review"]
            ):
                continue
            title_lines.append(line)
            if len(title_lines) >= 3:
                break

        return " ".join(title_lines) if title_lines else "Unknown Title"

    def _extract_abstract(self, text: str) -> str:
        """Extract abstract from full text."""
        # Try to find explicit abstract section
        patterns = [
            r'(?i)abstract\s*\n+(.*?)(?=\n\s*\d+[\.\s]+introduction|\n\s*1[\.\s]|\n\s*keywords)',
            r'(?i)abstract[:\s]+(.*?)(?=\n\n)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                abstract = " ".join(abstract.split())
                if 50 < len(abstract) < 3000:
                    return abstract

        return ""

    def _extract_sections(self, text: str) -> List[dict]:
        """Extract numbered sections from text."""
        sections = []
        matches = list(self.SECTION_PATTERN.finditer(text))

        for i, match in enumerate(matches):
            number = match.group(1)
            title = match.group(2).strip()

            # Content runs from this section to the next
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            sections.append({
                "number": number,
                "title": title,
                "content": content,
            })

        return sections


class GROBIDParser:
    """
    Academic paper parsing using GROBID.

    GROBID is specialized for academic documents and provides
    structured XML output with sections, references, etc.

    Requires GROBID server running (Java).
    """

    def __init__(self, grobid_url: str = "http://localhost:8070"):
        self.grobid_url = grobid_url

    def parse(self, pdf_path: Path, arxiv_id: str = "") -> Optional[ParsedPaper]:
        """
        Extract structured content using GROBID.
        """
        import requests
        from xml.etree import ElementTree as ET

        logger.info(f"Parsing {pdf_path} with GROBID")

        try:
            with open(pdf_path, "rb") as f:
                response = requests.post(
                    f"{self.grobid_url}/api/processFulltextDocument",
                    files={"input": f},
                    timeout=60,
                )

            if response.status_code != 200:
                logger.warning(f"GROBID returned {response.status_code}")
                return None

            tei_xml = response.text
            return self._parse_tei(tei_xml, arxiv_id)

        except requests.ConnectionError:
            logger.warning("GROBID server not available")
            return None
        except Exception as e:
            logger.warning(f"GROBID parsing failed: {e}")
            return None

    def _parse_tei(self, xml_text: str, arxiv_id: str) -> Optional[ParsedPaper]:
        """Parse GROBID TEI XML output."""
        from xml.etree import ElementTree as ET

        ns = {"tei": "http://www.tei-c.org/ns/1.0"}

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse GROBID XML: {e}")
            return None

        # Title
        title_el = root.find(".//tei:titleStmt/tei:title", ns)
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        # Abstract
        abstract_el = root.find(".//tei:profileDesc/tei:abstract", ns)
        abstract = ""
        if abstract_el is not None:
            abstract = " ".join(
                (p.text or "") for p in abstract_el.findall(".//tei:p", ns)
            )

        # Sections from body
        sections = []
        body = root.find(".//tei:body", ns)
        if body is not None:
            for div in body.findall("tei:div", ns):
                head = div.find("tei:head", ns)
                sec_title = head.text.strip() if head is not None and head.text else ""
                sec_num = head.get("n", "") if head is not None else ""
                paragraphs = [
                    (p.text or "") for p in div.findall("tei:p", ns)
                ]
                content = "\n\n".join(paragraphs)
                if sec_title or content:
                    sections.append({
                        "number": sec_num,
                        "title": sec_title,
                        "content": content,
                    })

        full_text = f"{title}\n\n{abstract}\n\n" + "\n\n".join(
            f"{s.get('number', '')} {s['title']}\n{s['content']}" for s in sections
        )

        return ParsedPaper(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            sections=sections,
            full_text=full_text,
            parser_used="grobid",
            parse_quality="good" if len(sections) >= 3 else "partial",
        )


class LLMParser:
    """
    Fallback parser using LLM to extract structure.

    Expensive and slow, but handles any document.
    Use only when other parsers fail.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def parse(self, pdf_path: Path, arxiv_id: str = "") -> Optional[ParsedPaper]:
        """
        Extract structure using LLM (last resort).

        Falls back to raw text extraction since LLM parsing
        requires async and is expensive.
        """
        logger.info(f"LLM parser fallback: extracting raw text from {pdf_path}")

        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            full_text = "\n\n".join(
                page.get_text("text") for page in doc
            )
            doc.close()

            if not full_text.strip():
                return None

            return ParsedPaper(
                arxiv_id=arxiv_id,
                title=arxiv_id,
                abstract="",
                sections=[],
                full_text=full_text,
                parser_used="llm_fallback_raw",
                parse_quality="fallback",
            )
        except Exception as e:
            logger.warning(f"LLM parser raw extraction failed: {e}")
            return None


async def parse_paper_pdf(
    pdf_path: Path,
    arxiv_id: str,
    config: Optional[ParserConfig] = None
) -> ParsedPaper:
    """
    Parse a paper PDF using fallback chain of parsers.

    Tries parsers in order until one succeeds:
    1. PyMuPDF (fast, simple)
    2. GROBID (accurate, needs server)
    3. LLM (expensive, universal)

    Returns ParsedPaper with best available extraction.
    """
    config = config or ParserConfig()

    for parser_name in config.parsers:
        try:
            if parser_name == "pymupdf":
                parser = PyMuPDFParser()
            elif parser_name == "grobid":
                if not config.grobid_url:
                    continue
                parser = GROBIDParser(config.grobid_url)
            elif parser_name == "llm":
                parser = LLMParser(config.llm_model)
            else:
                logger.warning(f"Unknown parser: {parser_name}")
                continue

            result = parser.parse(pdf_path, arxiv_id=arxiv_id)
            if result:
                logger.info(f"Successfully parsed {arxiv_id} with {parser_name}")
                return result

        except Exception as e:
            logger.warning(f"Parser {parser_name} failed for {arxiv_id}: {e}")
            continue

    raise ValueError(f"All parsers failed for {arxiv_id}")


async def download_paper_pdf(arxiv_id: str, output_dir: Path) -> Path:
    """
    Download paper PDF from ArXiv.

    Returns path to downloaded file.
    """
    # ArXiv PDF URL format
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    output_path = output_dir / f"{arxiv_id.replace('/', '_')}.pdf"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        logger.info(f"PDF already downloaded: {output_path}")
        return output_path

    logger.info(f"Downloading {pdf_url}")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(pdf_url)
        response.raise_for_status()

        output_path.write_bytes(response.content)

    logger.info(f"Downloaded to {output_path}")
    return output_path
