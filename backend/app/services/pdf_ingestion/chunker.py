"""
Document chunking with semantic boundaries and rich metadata.

Converts DocumentExtraction objects into ChunkRecord objects with:
- Page-aware chunking (chunks don't cross page boundaries without overlap)
- Semantic boundaries (headings, paragraph breaks)
- Rich metadata tracking (section hints, token counts, etc.)
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.pdf_service import DocumentExtraction, PageExtraction

logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    """A single text chunk with comprehensive metadata."""

    chunk_id: str  # Deterministic hash of document + page + index
    document_id: str
    source_file_name: str
    page_number: int  # Primary page number
    page_range: list[int] = field(default_factory=list)  # Pages this chunk spans
    chunk_index: int = 0  # Index within document
    section_hint: Optional[str] = None  # Heading or section context
    raw_text: str = ""  # Original text from PDF
    cleaned_text: str = ""  # Normalized text for indexing
    token_count_estimate: int = 0  # Approximate token count
    char_count: int = 0  # Exact character count
    has_table_content: bool = False  # Whether chunk contains tables


class DocumentChunker:
    """
    Converts DocumentExtraction into paginated chunks with semantic boundaries.

    Strategy:
    1. Process each page independently first
    2. Split pages by paragraphs (double newlines)
    3. Accumulate paragraphs until hitting chunk_size
    4. When encountering a heading, start a new chunk
    5. Add overlap from previous chunk's tail
    6. Skip chunks below min_chunk_size (merge with next)
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        min_chunk_size: int = 100,
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target characters per chunk
            chunk_overlap: Characters to overlap between chunks
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, doc: DocumentExtraction) -> list[ChunkRecord]:
        """
        Main entry point - chunk entire document.

        Args:
            doc: DocumentExtraction object with all pages

        Returns:
            List of ChunkRecord objects in document order
        """
        all_chunks = []
        global_chunk_index = 0

        for page_extraction in doc.pages:
            page_chunks = self._chunk_page(
                page_extraction,
                document_id=doc.document_id,
                source_file_name=doc.source_file_name,
                global_index_start=global_chunk_index,
            )

            # Verify and merge chunks if needed
            page_chunks = self._post_process_chunks(page_chunks)
            all_chunks.extend(page_chunks)
            global_chunk_index += len(page_chunks)

        # Add overlap across page boundaries (optional, currently disabled)
        # This could be enabled if cross-page context is needed

        logger.info(
            f"Chunked document {doc.document_id} into {len(all_chunks)} chunks"
        )
        return all_chunks

    def _chunk_page(
        self,
        page: PageExtraction,
        document_id: str,
        source_file_name: str,
        global_index_start: int,
    ) -> list[ChunkRecord]:
        """
        Chunk a single page using paragraph and heading boundaries.

        Args:
            page: PageExtraction object for one page
            document_id: UUID of parent document
            source_file_name: Original filename
            global_index_start: Starting chunk index for this page

        Returns:
            List of ChunkRecord objects for this page
        """
        text = page.cleaned_text
        if not text or not text.strip():
            return []

        chunks = []
        chunk_index = global_index_start

        # Split by paragraphs (double newlines)
        paragraphs = self._split_paragraphs(text)

        current_chunk_text = ""
        current_chunk_raw = ""
        current_section_hint = None
        overlap_text = ""

        for para_idx, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                continue

            # Check if this paragraph is a heading (from blocks)
            is_heading = self._is_paragraph_heading(paragraph, page.section_hints)

            # Decide whether to start new chunk
            potential_chunk = current_chunk_text + "\n" + paragraph
            potential_size = len(potential_chunk)

            # If we have content and either:
            # (a) adding this para exceeds chunk_size, or
            # (b) this para is a heading
            # then finalize current chunk
            if current_chunk_text and (potential_size > self.chunk_size or is_heading):
                # Create chunk from accumulated text
                chunk = self._create_chunk(
                    raw_text=current_chunk_raw,
                    document_id=document_id,
                    source_file_name=source_file_name,
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    section_hint=current_section_hint,
                    has_table=page.has_tables,
                )

                if chunk:  # Only add if not empty
                    chunks.append(chunk)
                    chunk_index += 1

                    # Prepare overlap for next chunk
                    overlap_text = self._get_overlap_tail(current_chunk_text)

                # Start new chunk with overlap
                current_chunk_text = overlap_text
                current_chunk_raw = overlap_text

            # Track section hints — use the matched heading text, not the full paragraph
            if is_heading:
                # Find which section_hint matched to use the clean heading name
                matched_hint = None
                para_lower = " ".join(paragraph.strip().lower().split())
                for hint in page.section_hints:
                    hint_lower = " ".join(hint.lower().strip().split())
                    if para_lower.startswith(hint_lower) or para_lower == hint_lower:
                        matched_hint = hint
                        break
                current_section_hint = matched_hint or paragraph.strip().split("\n")[0][:100]

            # Add paragraph to current chunk
            if current_chunk_text:
                current_chunk_text += "\n" + paragraph
                current_chunk_raw += "\n" + paragraph
            else:
                current_chunk_text = paragraph
                current_chunk_raw = paragraph

        # Don't forget final chunk
        if current_chunk_text.strip():
            chunk = self._create_chunk(
                raw_text=current_chunk_raw,
                document_id=document_id,
                source_file_name=source_file_name,
                page_number=page.page_number,
                chunk_index=chunk_index,
                section_hint=current_section_hint,
                has_table=page.has_tables,
            )
            if chunk:
                chunks.append(chunk)

        return chunks

    def _split_paragraphs(self, text: str) -> list[str]:
        """
        Split text into paragraphs by double newlines.

        Preserves single newlines within paragraphs.
        """
        # Split by double+ newlines
        paragraphs = re.split(r"\n\n+", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _is_paragraph_heading(
        self, paragraph: str, section_hints: list[str]
    ) -> bool:
        """
        Check if paragraph is likely a heading.

        Heuristics:
        - Normalized match with detected section hints (case-insensitive, whitespace-collapsed)
        - Short text (< 100 chars) that's in section_hints
        - All caps or mostly caps
        """
        para_clean = paragraph.strip()
        if not para_clean:
            return False

        # Normalize for comparison: lowercase, collapse whitespace
        para_normalized = " ".join(para_clean.lower().split())

        # Check against detected headings (normalized comparison)
        for hint in section_hints:
            hint_normalized = " ".join(hint.lower().strip().split())
            # Exact match
            if para_normalized == hint_normalized:
                return True
            # Paragraph starts with the heading text (common: heading + body on same line)
            if para_normalized.startswith(hint_normalized):
                return True
            # Short paragraph contained in a section hint
            if len(para_normalized) < 120 and hint_normalized in para_normalized:
                return True

        # Heuristic: all uppercase words (rough heading indicator)
        words = para_clean.split()
        if 0 < len(words) <= 6:
            uppercase_count = sum(1 for w in words if w.isupper() and len(w) > 1)
            if len(words) > 0 and uppercase_count / len(words) > 0.6:
                return True

        return False

    def _create_chunk(
        self,
        raw_text: str,
        document_id: str,
        source_file_name: str,
        page_number: int,
        chunk_index: int,
        section_hint: Optional[str] = None,
        has_table: bool = False,
    ) -> Optional[ChunkRecord]:
        """
        Create a ChunkRecord from accumulated text.

        Returns None if text is too short (below min_chunk_size).
        """
        raw_text = raw_text.strip()
        if not raw_text:
            return None

        char_count = len(raw_text)
        if char_count < self.min_chunk_size:
            logger.debug(
                f"Skipping chunk {chunk_index} on page {page_number} "
                f"(size {char_count} < {self.min_chunk_size})"
            )
            return None

        # Generate deterministic chunk ID
        chunk_id = self.generate_chunk_id(document_id, page_number, chunk_index)

        # Estimate tokens (rough: ~4 chars per token)
        token_estimate = max(1, char_count // 4)

        # Clean text for indexing
        cleaned_text = self._clean_text_for_indexing(raw_text)

        return ChunkRecord(
            chunk_id=chunk_id,
            document_id=document_id,
            source_file_name=source_file_name,
            page_number=page_number,
            page_range=[page_number],  # Single page for now
            chunk_index=chunk_index,
            section_hint=section_hint,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            token_count_estimate=token_estimate,
            char_count=char_count,
            has_table_content=has_table,
        )

    def _get_overlap_tail(self, text: str) -> str:
        """
        Extract tail of text for overlap with next chunk.

        Takes the last ~chunk_overlap characters, but respects word boundaries.
        """
        if len(text) <= self.chunk_overlap:
            return text

        # Find last ~chunk_overlap chars
        tail = text[-self.chunk_overlap :]

        # Find the first space to start at a word boundary
        first_space = tail.find(" ")
        if first_space > 0 and first_space < len(tail) - 10:
            tail = tail[first_space + 1 :]

        return tail.strip()

    def _post_process_chunks(self, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        """
        Post-process chunks: merge too-small chunks with neighbors.

        Args:
            chunks: List of chunks from a single page

        Returns:
            Processed list with small chunks merged
        """
        if not chunks or len(chunks) == 1:
            return chunks

        result = []
        i = 0

        while i < len(chunks):
            chunk = chunks[i]

            # If chunk is too small, try to merge with next
            if chunk.char_count < self.min_chunk_size and i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                # Merge by combining texts
                merged = ChunkRecord(
                    chunk_id=self.generate_chunk_id(
                        chunk.document_id,
                        chunk.page_number,
                        chunk.chunk_index,
                    ),
                    document_id=chunk.document_id,
                    source_file_name=chunk.source_file_name,
                    page_number=chunk.page_number,
                    page_range=chunk.page_range,
                    chunk_index=chunk.chunk_index,
                    section_hint=chunk.section_hint or next_chunk.section_hint,
                    raw_text=chunk.raw_text + "\n\n" + next_chunk.raw_text,
                    cleaned_text=chunk.cleaned_text
                    + " "
                    + next_chunk.cleaned_text,
                    token_count_estimate=chunk.token_count_estimate
                    + next_chunk.token_count_estimate,
                    char_count=chunk.char_count + next_chunk.char_count,
                    has_table_content=chunk.has_table_content
                    or next_chunk.has_table_content,
                )
                result.append(merged)
                i += 2  # Skip both chunks
            else:
                result.append(chunk)
                i += 1

        return result

    def _clean_text_for_indexing(self, text: str) -> str:
        """
        Normalize text for indexing / embedding.

        - Lowercase
        - Remove extra whitespace
        - Keep alphanumeric and basic punctuation
        """
        # Normalize whitespace
        text = " ".join(text.split())
        # Lowercase for consistency
        text = text.lower()
        return text

    @staticmethod
    def generate_chunk_id(document_id: str, page_number: int, chunk_index: int) -> str:
        """
        Generate deterministic chunk ID from document + page + index.

        Ensures reproducible IDs across runs.
        """
        key = f"{document_id}:{page_number}:{chunk_index}"
        hash_digest = hashlib.sha256(key.encode()).hexdigest()
        return hash_digest[:16]  # First 16 hex chars

    @staticmethod
    def generate_preview(text: str, max_length: int = 200) -> str:
        """
        Generate a preview string from text.

        Truncates at word boundary if needed.
        """
        if len(text) <= max_length:
            return text

        preview = text[:max_length]
        last_space = preview.rfind(" ")
        if last_space > 50:
            preview = preview[:last_space] + "..."
        else:
            preview = preview + "..."

        return preview
