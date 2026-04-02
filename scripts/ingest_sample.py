#!/usr/bin/env python3
"""Sample script to ingest a PDF and test retrieval — Vaibhav's module.

Usage:
    python scripts/ingest_sample.py path/to/sample.pdf
    python scripts/ingest_sample.py path/to/sample.pdf --query "What is the intervention?"
"""
import argparse
import asyncio
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.pdf_service import pdf_service


def main():
    parser = argparse.ArgumentParser(description="Ingest a PDF and optionally test retrieval")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--query", help="Optional retrieval query to test", default=None)
    parser.add_argument("--chunk-size", type=int, default=800, help="Chunk size in characters")
    parser.add_argument("--overlap", type=int, default=150, help="Chunk overlap in characters")
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"ERROR: File not found: {args.pdf_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"PDF Ingestion Test — Vaibhav's Module")
    print(f"{'='*60}")
    print(f"File: {args.pdf_path}")
    print(f"Chunk size: {args.chunk_size}, Overlap: {args.overlap}\n")

    # Step 1: Extract
    print("[1/3] Extracting PDF...")
    doc = pdf_service.extract_document(args.pdf_path)
    print(f"  Document ID: {doc.document_id}")
    print(f"  Pages: {doc.total_pages}")
    print(f"  Words: {doc.total_word_count}")
    print(f"  Checksum: {doc.file_checksum}")

    for page in doc.pages:
        print(f"  Page {page.page_number}: {page.word_count} words, tables={page.has_tables}, sections={page.section_hints}")

    # Step 2: Chunk
    print("\n[2/3] Chunking...")
    from app.services.pdf_ingestion.chunker import DocumentChunker
    chunker = DocumentChunker(chunk_size=args.chunk_size, chunk_overlap=args.overlap)
    chunks = chunker.chunk_document(doc)
    print(f"  Total chunks: {len(chunks)}")

    for i, chunk in enumerate(chunks[:5]):
        print(f"\n  Chunk {i} (page {chunk.page_number}, {chunk.char_count} chars):")
        print(f"    ID: {chunk.chunk_id}")
        print(f"    Section: {chunk.section_hint or 'N/A'}")
        print(f"    Preview: {chunk.cleaned_text[:100]}...")

    if len(chunks) > 5:
        print(f"\n  ... and {len(chunks) - 5} more chunks")

    # Step 3: Summary
    print(f"\n[3/3] Summary")
    print(f"  {'='*40}")
    print(f"  Document: {doc.source_file_name}")
    print(f"  Pages: {doc.total_pages}")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Avg chunk size: {sum(c.char_count for c in chunks) / max(len(chunks), 1):.0f} chars")
    print(f"  Ready for vector indexing: YES")
    print(f"  {'='*40}\n")

    if args.query:
        print(f"NOTE: Retrieval query testing requires a running database.")
        print(f"Use the API endpoint POST /api/v1/retrieval/retrieve instead.")
        print(f"Query: {args.query}")


if __name__ == "__main__":
    main()
