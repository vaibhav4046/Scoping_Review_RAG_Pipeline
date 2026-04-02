#!/usr/bin/env python3
"""
Test script for new PDF service and chunker.

Verifies:
- DocumentExtraction structure and metadata
- PageExtraction with block-level analysis
- ChunkRecord generation
- Backward compatibility with legacy methods
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.pdf_service import PDFService, DocumentExtraction, PageExtraction, BlockInfo
from app.services.pdf_ingestion import DocumentChunker, ChunkRecord


def test_dataclass_structures():
    """Test that dataclass structures are properly defined."""
    print("Testing dataclass structures...")

    # BlockInfo
    block = BlockInfo(
        text="Sample text",
        block_type="heading",
        bbox=(0, 0, 100, 100),
        font_size=14.0,
        is_bold=True,
        page_number=1,
    )
    assert block.text == "Sample text"
    assert block.block_type == "heading"
    print("  ✓ BlockInfo structure OK")

    # PageExtraction
    page = PageExtraction(
        page_number=1,
        raw_text="Raw text",
        cleaned_text="Cleaned text",
        blocks=[block],
        section_hints=["Introduction"],
        has_tables=False,
        word_count=2,
    )
    assert page.page_number == 1
    assert len(page.blocks) == 1
    print("  ✓ PageExtraction structure OK")

    # DocumentExtraction
    doc = DocumentExtraction(
        document_id="test-123",
        source_file_name="test.pdf",
        source_file_path="/path/to/test.pdf",
        total_pages=1,
        extraction_timestamp="2026-04-01T00:00:00",
        pages=[page],
        full_text="Full text",
        file_checksum="abc123",
        total_word_count=2,
    )
    assert doc.document_id == "test-123"
    assert doc.total_pages == 1
    print("  ✓ DocumentExtraction structure OK")


def test_chunker_structures():
    """Test ChunkRecord dataclass."""
    print("\nTesting chunker structures...")

    chunk = ChunkRecord(
        chunk_id="chunk-001",
        document_id="doc-123",
        source_file_name="test.pdf",
        page_number=1,
        page_range=[1],
        chunk_index=0,
        section_hint="Introduction",
        raw_text="This is a test chunk.",
        cleaned_text="this is a test chunk",
        token_count_estimate=5,
        char_count=20,
        has_table_content=False,
    )
    assert chunk.chunk_id == "chunk-001"
    assert chunk.page_number == 1
    print("  ✓ ChunkRecord structure OK")


def test_pdf_service_methods():
    """Test PDFService method signatures."""
    print("\nTesting PDFService methods...")

    service = PDFService(chunk_size=1000, chunk_overlap=200)

    # Check methods exist
    assert hasattr(service, "extract_document")
    assert hasattr(service, "extract_text")
    assert hasattr(service, "extract_pages")
    assert hasattr(service, "chunk_text")
    assert hasattr(service, "extract_and_chunk")
    assert hasattr(service, "extract_and_chunk_rich")
    print("  ✓ All PDFService methods exist")

    # Test chunk_text with dummy input
    chunks = service.chunk_text("word " * 500)  # 500 words
    assert len(chunks) > 0
    assert all("text" in c for c in chunks)
    assert all("index" in c for c in chunks)
    assert all("token_count" in c for c in chunks)
    print(f"  ✓ chunk_text works (created {len(chunks)} chunks)")


def test_chunker_methods():
    """Test DocumentChunker method signatures."""
    print("\nTesting DocumentChunker methods...")

    chunker = DocumentChunker(chunk_size=800, chunk_overlap=150, min_chunk_size=100)

    # Check methods exist
    assert hasattr(chunker, "chunk_document")
    assert hasattr(chunker, "generate_chunk_id")
    assert hasattr(chunker, "generate_preview")
    print("  ✓ All DocumentChunker methods exist")

    # Test generate_chunk_id
    chunk_id = DocumentChunker.generate_chunk_id("doc-123", 1, 0)
    assert len(chunk_id) == 16
    assert all(c in "0123456789abcdef" for c in chunk_id)
    print(f"  ✓ generate_chunk_id works: {chunk_id}")

    # Test generate_preview
    text = "This is a very long text that should be truncated at word boundary."
    preview = DocumentChunker.generate_preview(text, max_length=20)
    assert len(preview) <= 30  # Some buffer for "..."
    print(f"  ✓ generate_preview works: '{preview}'")

    # Test on synthetic document (with sufficient text for min_chunk_size)
    long_text = """Introduction

This is a longer paragraph with multiple sentences to ensure we have enough content.
It contains more than 100 characters which is the minimum chunk size threshold.
We need sufficient text to make meaningful chunks.

Another paragraph here with additional content. This should help demonstrate the chunking
behavior and ensure that our chunks are properly created and tracked with metadata."""

    block = BlockInfo(
        text="Introduction", block_type="heading", page_number=1
    )
    page = PageExtraction(
        page_number=1,
        raw_text=long_text,
        cleaned_text=long_text,
        blocks=[block],
        section_hints=["Introduction"],
        has_tables=False,
        word_count=len(long_text.split()),
    )
    doc = DocumentExtraction(
        document_id="test-doc-123",
        source_file_name="test.pdf",
        source_file_path="/test.pdf",
        total_pages=1,
        extraction_timestamp="2026-04-01T00:00:00",
        pages=[page],
        full_text=long_text,
        file_checksum="abc123",
        total_word_count=len(long_text.split()),
    )

    chunks = chunker.chunk_document(doc)
    assert len(chunks) > 0
    assert all(isinstance(c, ChunkRecord) for c in chunks)
    print(f"  ✓ chunk_document works (created {len(chunks)} chunks from synthetic doc)")


def test_backward_compatibility():
    """Test that legacy methods still work."""
    print("\nTesting backward compatibility...")

    service = PDFService()

    # Test legacy chunk_text
    text = "word " * 250
    chunks = service.chunk_text(text)
    assert len(chunks) > 0
    assert "index" in chunks[0]
    assert "token_count" in chunks[0]
    print("  ✓ Legacy chunk_text still works")

    # Test legacy extract_and_chunk
    # (Will fail on file not found, but we can test the method exists)
    try:
        result = service.extract_and_chunk("/nonexistent.pdf")
        assert result == []
    except FileNotFoundError:
        pass
    print("  ✓ Legacy extract_and_chunk still works")


if __name__ == "__main__":
    print("=" * 60)
    print("PDF Service and Chunker Test Suite")
    print("=" * 60)

    try:
        test_dataclass_structures()
        test_chunker_structures()
        test_pdf_service_methods()
        test_chunker_methods()
        test_backward_compatibility()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
