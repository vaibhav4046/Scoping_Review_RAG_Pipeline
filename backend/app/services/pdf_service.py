"""Production-quality PDF ingestion service with block-level extraction and rich metadata."""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import fitz  # PyMuPDF

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class BlockInfo:
    """Rich information about a text block extracted from a PDF page."""
    text: str
    block_type: str  # "text", "heading", "table_row", "image_caption", "code"
    bbox: Optional[tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)
    font_size: Optional[float] = None
    is_bold: bool = False
    page_number: int = 0


@dataclass
class PageExtraction:
    """Extracted content and metadata from a single PDF page."""
    page_number: int
    raw_text: str
    cleaned_text: str
    blocks: list[BlockInfo] = field(default_factory=list)
    section_hints: list[str] = field(default_factory=list)  # Detected headings
    has_tables: bool = False
    word_count: int = 0


@dataclass
class DocumentExtraction:
    """Complete extraction result for an entire PDF document."""
    document_id: str
    source_file_name: str
    source_file_path: str
    total_pages: int
    extraction_timestamp: str
    pages: list[PageExtraction] = field(default_factory=list)
    full_text: str = ""
    file_checksum: str = ""  # MD5 for deduplication
    total_word_count: int = 0


class PDFService:
    """Production-quality PDF text extraction with block-level analysis and rich metadata."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.median_font_size_cache = {}

    def extract_document(
        self, pdf_path: str, document_id: Optional[str] = None
    ) -> DocumentExtraction:
        """
        Extract entire PDF document with full metadata and structure analysis.

        Args:
            pdf_path: Path to PDF file
            document_id: Optional UUID; auto-generated if not provided

        Returns:
            DocumentExtraction dataclass with all metadata and page extractions
        """
        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        pdf_path = os.path.abspath(pdf_path)
        file_name = os.path.basename(pdf_path)
        document_id = document_id or str(uuid4())

        try:
            doc = fitz.open(pdf_path)

            # Calculate file checksum
            file_checksum = self._compute_file_checksum(pdf_path)

            # Extract all pages
            pages = []
            full_text_parts = []
            total_word_count = 0

            for page_num in range(len(doc)):
                page_extraction = self._extract_page(doc, page_num, document_id)
                pages.append(page_extraction)
                full_text_parts.append(page_extraction.cleaned_text)
                total_word_count += page_extraction.word_count

            doc.close()

            full_text = "\n\n".join(full_text_parts)

            extraction = DocumentExtraction(
                document_id=document_id,
                source_file_name=file_name,
                source_file_path=pdf_path,
                total_pages=len(pages),
                extraction_timestamp=datetime.now(timezone.utc).isoformat(),
                pages=pages,
                full_text=full_text,
                file_checksum=file_checksum,
                total_word_count=total_word_count,
            )

            logger.info(
                f"Extracted document {document_id} from {file_name}: "
                f"{len(pages)} pages, {total_word_count} words"
            )
            return extraction

        except Exception as e:
            logger.error(f"PDF extraction failed for {pdf_path}: {e}", exc_info=True)
            raise

    def extract_text(self, pdf_path: str) -> Optional[str]:
        """
        Legacy compatibility method - extract plain text from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Concatenated text from all pages, or None if extraction fails
        """
        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return None

        try:
            doc = fitz.open(pdf_path)
            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(text)
            doc.close()

            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} chars from {pdf_path}")
            return full_text if full_text.strip() else None

        except Exception as e:
            logger.error(f"PDF extraction failed for {pdf_path}: {e}")
            return None

    def extract_pages(self, pdf_path: str) -> list[PageExtraction]:
        """
        Extract structured content for each page with block-level analysis.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of PageExtraction objects
        """
        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return []

        try:
            doc = fitz.open(pdf_path)
            pages = []
            for page_num in range(len(doc)):
                page_extraction = self._extract_page(doc, page_num)
                pages.append(page_extraction)
            doc.close()
            return pages

        except Exception as e:
            logger.error(f"Page extraction failed for {pdf_path}: {e}", exc_info=True)
            return []

    def chunk_text(self, text: str) -> list[dict]:
        """
        Legacy compatibility method - simple word-based chunking with overlap.

        Args:
            text: Text to chunk

        Returns:
            List of dicts with keys: text, index, token_count
        """
        if not text:
            return []

        words = text.split()
        chunks = []
        chunk_idx = 0
        i = 0

        while i < len(words):
            chunk_words = words[i : i + self.chunk_size]
            chunk_text = " ".join(chunk_words)

            chunks.append({
                "text": chunk_text,
                "index": chunk_idx,
                "token_count": len(chunk_words),
            })

            chunk_idx += 1
            i += max(self.chunk_size - self.chunk_overlap, 1)

        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks

    def extract_and_chunk(self, pdf_path: str) -> list[dict]:
        """
        Legacy compatibility method - extract and chunk in one call.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of chunk dicts
        """
        text = self.extract_text(pdf_path)
        if not text:
            return []
        return self.chunk_text(text)

    def extract_and_chunk_rich(
        self, pdf_path: str, document_id: Optional[str] = None
    ) -> tuple[DocumentExtraction, list]:
        """
        Full extraction with chunking using rich metadata.
        Primary method for new code.

        Args:
            pdf_path: Path to PDF file
            document_id: Optional document UUID

        Returns:
            Tuple of (DocumentExtraction, list of chunk records)
        """
        doc_extraction = self.extract_document(pdf_path, document_id)

        # Import here to avoid circular imports
        from app.services.pdf_ingestion.chunker import DocumentChunker

        chunker = DocumentChunker(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        chunks = chunker.chunk_document(doc_extraction)

        logger.info(
            f"Document {doc_extraction.document_id} chunked into {len(chunks)} chunks"
        )
        return doc_extraction, chunks

    # ─── Internal Methods ───

    def _extract_page(
        self, doc: fitz.Document, page_num: int, document_id: str = ""
    ) -> PageExtraction:
        """
        Extract structured content from a single page.

        Uses dict format for block-level analysis and metadata extraction.
        """
        page = doc[page_num]

        # Get dict format for block-level analysis
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])

        # Also get plain text for fallback
        raw_text = page.get_text("text")

        # Extract block information
        block_infos = []
        font_sizes = []
        section_hints = []
        has_tables = False

        for block in blocks:
            if block["type"] == 0:  # Text block
                block_text = ""
                block_font_size = None
                is_bold = False

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        block_text += span.get("text", "")

                        # Track font size for heading detection
                        font_info = span.get("size", 0)
                        if font_info:
                            font_sizes.append(font_info)
                            block_font_size = font_info

                        # Check for bold
                        flags = span.get("flags", 0)
                        if flags & 16:  # Bold flag
                            is_bold = True

                if block_text.strip():
                    bbox = block.get("bbox")
                    block_info = BlockInfo(
                        text=block_text.strip(),
                        block_type="text",
                        bbox=bbox,
                        font_size=block_font_size,
                        is_bold=is_bold,
                        page_number=page_num + 1,
                    )
                    block_infos.append(block_info)

            elif block["type"] == 1:  # Image block
                pass

            elif block["type"] == 3:  # Table block
                has_tables = True
                bbox = block.get("bbox")
                table_text = f"[TABLE at {bbox}]"
                block_info = BlockInfo(
                    text=table_text,
                    block_type="table_row",
                    bbox=bbox,
                    page_number=page_num + 1,
                )
                block_infos.append(block_info)

        # Detect headings: text that is bold OR has font size > body_font * 1.1
        # Use MODE (most common font) as body font — more robust than median
        if font_sizes:
            from collections import Counter
            font_counter = Counter(round(fs, 1) for fs in font_sizes)
            body_font_size = font_counter.most_common(1)[0][0]
            heading_threshold = body_font_size * 1.1

            for block_info in block_infos:
                if (
                    block_info.is_bold
                    or (block_info.font_size and block_info.font_size > heading_threshold)
                ):
                    block_info.block_type = "heading"
                    section_hints.append(block_info.text)

        # Build cleaned_text from blocks with proper paragraph breaks
        # Use double newlines before headings so the chunker can split on them
        cleaned_parts = []
        for block_info in block_infos:
            block_text = block_info.text.strip()
            if not block_text:
                continue
            if block_info.block_type == "heading" and cleaned_parts:
                cleaned_parts.append("\n\n" + block_text)
            else:
                cleaned_parts.append(block_text)
        cleaned_text = "\n".join(cleaned_parts) if cleaned_parts else self._clean_text(raw_text)
        word_count = len(cleaned_text.split())

        return PageExtraction(
            page_number=page_num + 1,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            blocks=block_infos,
            section_hints=section_hints,
            has_tables=has_tables,
            word_count=word_count,
        )

    def _clean_text(self, text: str) -> str:
        """
        Normalize whitespace while preserving structure.

        - Collapses multiple spaces to single space
        - Preserves paragraph breaks (double newlines)
        - Removes excessive blank lines
        """
        # First, normalize line endings
        text = text.replace("\r\n", "\n")

        # Collapse multiple spaces on same line
        lines = text.split("\n")
        lines = [" ".join(line.split()) for line in lines]
        text = "\n".join(lines)

        # Collapse excessive blank lines (more than 2 newlines)
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

    def _compute_file_checksum(self, file_path: str) -> str:
        """Compute MD5 checksum of file for deduplication."""
        md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute checksum for {file_path}: {e}")
            return ""


# ─── Module-level singleton for backward compatibility ───
pdf_service = PDFService()
