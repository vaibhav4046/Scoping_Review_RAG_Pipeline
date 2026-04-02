"""Tests for document chunker — Vaibhav's module."""
import pytest

from app.services.pdf_service import PageExtraction, DocumentExtraction, BlockInfo
from app.services.pdf_ingestion.chunker import DocumentChunker, ChunkRecord


class TestDocumentChunker:
    def setup_method(self):
        self.chunker = DocumentChunker(chunk_size=200, chunk_overlap=50, min_chunk_size=30)

    def _make_doc(self, pages_text: list[str]) -> DocumentExtraction:
        """Helper to create a DocumentExtraction from page texts."""
        pages = []
        for i, text in enumerate(pages_text):
            pages.append(PageExtraction(
                page_number=i + 1,
                raw_text=text,
                cleaned_text=text,
                blocks=[BlockInfo(text=text, block_type="text", page_number=i+1)],
                section_hints=[],
                has_tables=False,
                word_count=len(text.split()),
            ))
        return DocumentExtraction(
            document_id="test-doc-123",
            source_file_name="test.pdf",
            source_file_path="/tmp/test.pdf",
            total_pages=len(pages),
            extraction_timestamp="2026-01-01T00:00:00",
            pages=pages,
            full_text="\n\n".join(pages_text),
            file_checksum="abc123",
            total_word_count=sum(len(t.split()) for t in pages_text),
        )

    def test_chunk_single_page(self):
        doc = self._make_doc(["This is a simple test paragraph with enough words to form at least one chunk of text."])
        chunks = self.chunker.chunk_document(doc)
        assert len(chunks) >= 1
        assert all(isinstance(c, ChunkRecord) for c in chunks)

    def test_chunk_preserves_page_number(self):
        # Use text long enough to exceed min_chunk_size (30 chars)
        doc = self._make_doc([
            "Page one has enough content to exceed the minimum chunk size threshold for testing.",
            "Page two also has enough content to exceed the minimum chunk size threshold for testing.",
        ])
        chunks = self.chunker.chunk_document(doc)
        assert len(chunks) >= 1
        page_numbers = {c.page_number for c in chunks}
        assert 1 in page_numbers or 2 in page_numbers

    def test_chunk_preserves_document_id(self):
        doc = self._make_doc(["Some text content for testing."])
        chunks = self.chunker.chunk_document(doc)
        for chunk in chunks:
            assert chunk.document_id == "test-doc-123"
            assert chunk.source_file_name == "test.pdf"

    def test_deterministic_chunk_ids(self):
        """Same input should produce same chunk IDs."""
        id1 = DocumentChunker.generate_chunk_id("doc1", 1, 0)
        id2 = DocumentChunker.generate_chunk_id("doc1", 1, 0)
        id3 = DocumentChunker.generate_chunk_id("doc1", 1, 1)
        assert id1 == id2  # Same input = same ID
        assert id1 != id3  # Different input = different ID

    def test_chunk_id_format(self):
        cid = DocumentChunker.generate_chunk_id("doc1", 1, 0)
        assert isinstance(cid, str)
        assert len(cid) == 16

    def test_generate_preview(self):
        text = "Hello world " * 50
        preview = DocumentChunker.generate_preview(text, max_length=50)
        assert len(preview) <= 53  # 50 + "..."

    def test_empty_document(self):
        doc = self._make_doc([])
        chunks = self.chunker.chunk_document(doc)
        assert chunks == []

    def test_multi_page_long_text(self):
        # Use paragraph breaks (\n\n) so the chunker can split within each page
        text1 = "\n\n".join(["First page paragraph. " * 20 for _ in range(5)])
        text2 = "\n\n".join(["Second page paragraph. " * 20 for _ in range(5)])
        doc = self._make_doc([text1, text2])
        chunks = self.chunker.chunk_document(doc)
        assert len(chunks) > 2  # Should create multiple chunks across two pages

    def test_chunk_record_fields(self):
        doc = self._make_doc(["Test content for chunk record field validation."])
        chunks = self.chunker.chunk_document(doc)
        if chunks:
            chunk = chunks[0]
            assert hasattr(chunk, 'chunk_id')
            assert hasattr(chunk, 'document_id')
            assert hasattr(chunk, 'page_number')
            assert hasattr(chunk, 'chunk_index')
            assert hasattr(chunk, 'raw_text')
            assert hasattr(chunk, 'cleaned_text')
            assert hasattr(chunk, 'token_count_estimate')
            assert hasattr(chunk, 'char_count')
