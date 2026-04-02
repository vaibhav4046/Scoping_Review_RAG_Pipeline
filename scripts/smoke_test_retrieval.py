#!/usr/bin/env python3
"""Smoke test: verify PDF extraction → chunking pipeline works end-to-end.

Usage:
    python scripts/smoke_test_retrieval.py [path/to/pdf]

If no PDF is provided, creates a minimal test PDF.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def create_test_pdf(path: str):
    """Create a minimal test PDF with fitz."""
    import fitz
    doc = fitz.open()

    # Page 1
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Introduction", fontsize=16)
    page1.insert_text((72, 100), "This is a clinical trial studying the effects of Drug X on patients with condition Y. "
                       "The study population consisted of 200 adults aged 18-65 with confirmed diagnosis.", fontsize=11)
    page1.insert_text((72, 140), "Methods", fontsize=16)
    page1.insert_text((72, 168), "We conducted a randomized controlled trial with a 1:1 allocation ratio. "
                       "The intervention group received Drug X 100mg daily. The control group received placebo.", fontsize=11)

    # Page 2
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Results", fontsize=16)
    page2.insert_text((72, 100), "Primary outcome: Survival rate was 85% in the intervention group vs 70% in the control. "
                       "Secondary outcome: Quality of life scores improved by 2.3 points (p<0.001).", fontsize=11)
    page2.insert_text((72, 140), "Discussion", fontsize=16)
    page2.insert_text((72, 168), "These findings suggest Drug X is effective for treating condition Y. "
                       "The sample size provides adequate statistical power.", fontsize=11)

    doc.save(path)
    doc.close()
    return path


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None

    if not pdf_path:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        pdf_path = tmp.name
        tmp.close()
        print(f"Creating test PDF at {pdf_path}...")
        create_test_pdf(pdf_path)

    print(f"\n{'='*60}")
    print("SMOKE TEST: PDF -> Extract -> Chunk Pipeline")
    print(f"{'='*60}\n")

    # Test 1: PDF extraction
    print("[TEST 1] PDF extraction...")
    from app.services.pdf_service import pdf_service
    doc = pdf_service.extract_document(pdf_path)
    assert doc.total_pages > 0, f"FAIL: Expected pages > 0, got {doc.total_pages}"
    assert doc.full_text.strip(), "FAIL: No text extracted"
    print(f"  PASS: {doc.total_pages} pages, {doc.total_word_count} words")

    # Test 2: Chunking
    print("[TEST 2] Chunking...")
    from app.services.pdf_ingestion.chunker import DocumentChunker
    chunker = DocumentChunker(chunk_size=300, chunk_overlap=50)
    chunks = chunker.chunk_document(doc)
    assert len(chunks) > 0, "FAIL: No chunks produced"
    for chunk in chunks:
        assert chunk.chunk_id, "FAIL: Missing chunk_id"
        assert chunk.document_id == doc.document_id, "FAIL: document_id mismatch"
        assert chunk.page_number > 0, "FAIL: Invalid page_number"
    print(f"  PASS: {len(chunks)} chunks with valid metadata")

    # Test 3: Metadata integrity
    print("[TEST 3] Metadata integrity...")
    all_pages = {c.page_number for c in chunks}
    assert len(all_pages) > 0, "FAIL: No page numbers found"
    for chunk in chunks:
        assert chunk.source_file_name, "FAIL: Missing source_file_name"
        assert chunk.char_count > 0, "FAIL: char_count is 0"
    print(f"  PASS: Pages covered: {sorted(all_pages)}")

    # Test 4: Chunk ID determinism
    print("[TEST 4] Chunk ID determinism...")
    id1 = DocumentChunker.generate_chunk_id("test", 1, 0)
    id2 = DocumentChunker.generate_chunk_id("test", 1, 0)
    assert id1 == id2, "FAIL: Chunk IDs not deterministic"
    print(f"  PASS: Deterministic chunk IDs confirmed")

    # Test 5: Legacy compatibility
    print("[TEST 5] Legacy compatibility...")
    text = pdf_service.extract_text(pdf_path)
    assert text and len(text) > 0, "FAIL: Legacy extract_text returned nothing"
    legacy_chunks = pdf_service.extract_and_chunk(pdf_path)
    assert len(legacy_chunks) > 0, "FAIL: Legacy extract_and_chunk returned nothing"
    assert "text" in legacy_chunks[0], "FAIL: Legacy chunk format missing 'text' key"
    print(f"  PASS: Legacy methods work correctly")

    # Test 6: Rich extraction
    print("[TEST 6] Rich extraction + chunking...")
    doc2, chunks2 = pdf_service.extract_and_chunk_rich(pdf_path)
    assert isinstance(doc2, type(doc)), "FAIL: Wrong return type"
    assert len(chunks2) > 0, "FAIL: No rich chunks"
    print(f"  PASS: extract_and_chunk_rich returns {len(chunks2)} chunks")

    print(f"\n{'='*60}")
    print(f"ALL SMOKE TESTS PASSED")
    print(f"{'='*60}\n")

    # Cleanup temp file
    if len(sys.argv) <= 1:
        os.unlink(pdf_path)


if __name__ == "__main__":
    main()
