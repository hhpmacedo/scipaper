"""
PDF parsing for academic papers.

Attempts multiple strategies to extract structured text from paper PDFs.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

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
    llm_model: str = "claude-3-5-sonnet-20241022"
    
    def __post_init__(self):
        if self.parsers is None:
            self.parsers = ["pymupdf", "grobid", "llm"]


class PyMuPDFParser:
    """
    Fast PDF text extraction using PyMuPDF (fitz).
    
    Good for simple layouts, struggles with complex academic formatting.
    """
    
    def parse(self, pdf_path: Path) -> Optional[ParsedPaper]:
        """
        Extract text from PDF using PyMuPDF.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF not installed")
            return None
        
        # TODO: Implement PyMuPDF extraction
        #
        # 1. Open PDF with fitz
        # 2. Extract text from each page
        # 3. Try to identify section headers
        # 4. Build structured output
        
        logger.info(f"Parsing {pdf_path} with PyMuPDF")
        raise NotImplementedError("PyMuPDF parser not yet implemented")


class GROBIDParser:
    """
    Academic paper parsing using GROBID.
    
    GROBID is specialized for academic documents and provides
    structured XML output with sections, references, etc.
    
    Requires GROBID server running (Java).
    """
    
    def __init__(self, grobid_url: str = "http://localhost:8070"):
        self.grobid_url = grobid_url
    
    def parse(self, pdf_path: Path) -> Optional[ParsedPaper]:
        """
        Extract structured content using GROBID.
        """
        # TODO: Implement GROBID client
        #
        # 1. Send PDF to GROBID /api/processFulltextDocument
        # 2. Parse TEI XML response
        # 3. Extract sections, figures, tables
        # 4. Build structured output
        
        logger.info(f"Parsing {pdf_path} with GROBID")
        raise NotImplementedError("GROBID parser not yet implemented")


class LLMParser:
    """
    Fallback parser using LLM to extract structure.
    
    Expensive and slow, but handles any document.
    Use only when other parsers fail.
    """
    
    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
    
    def parse(self, pdf_path: Path) -> Optional[ParsedPaper]:
        """
        Extract structure using LLM (last resort).
        """
        # TODO: Implement LLM extraction
        #
        # 1. Extract raw text (any method)
        # 2. Send to LLM with extraction prompt
        # 3. Parse structured output
        
        logger.info(f"Parsing {pdf_path} with LLM fallback")
        raise NotImplementedError("LLM parser not yet implemented")


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
            
            result = parser.parse(pdf_path)
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
    import httpx
    
    # ArXiv PDF URL format
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    output_path = output_dir / f"{arxiv_id.replace('/', '_')}.pdf"
    
    if output_path.exists():
        logger.info(f"PDF already downloaded: {output_path}")
        return output_path
    
    logger.info(f"Downloading {pdf_url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(pdf_url, follow_redirects=True)
        response.raise_for_status()
        
        output_path.write_bytes(response.content)
    
    logger.info(f"Downloaded to {output_path}")
    return output_path
