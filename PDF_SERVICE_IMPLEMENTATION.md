# PDF Processing & RAG Workstream Implementation

## Overview

This document describes the production-quality PDF ingestion and chunking system for the medical scoping review project. The implementation provides:

- **Block-level extraction** using PyMuPDF (`fitz`) with rich metadata
- **Page-aware chunking** that respects document structure
- **Semantic boundaries** using heading and paragraph detection
- **Rich metadata** tracking including document IDs, checksums, page numbers, and section hints
- **Backward compatibility** with legacy methods

## Architecture

### Files Created/Modified

```
backend/app/services/
├── pdf_service.py                    (REWRITTEN - production quality)
└── pdf_ingestion/
    ├── __init__.py                   (NEW)
    └── chunker.py                    (NEW)
```

## Core Components

### 1. PDF Service (`pdf_service.py`)

#### Dataclasses

**BlockInfo**: Represents a single text block extracted from a PDF page
- `text`: Content of the block
- `block_type`: Classification ("text", "heading", "table_row", "image_caption", "code")
- `bbox`: Bounding box coordinates (x0, y0, x1, y1)
- `font_size`: Point size of font
- `is_bold`: Boolean flag
- `page_number`: Source page (1-indexed)

**PageExtraction**: Structured content from a single PDF page
- `page_number`: Page number (1-indexed)
- `raw_text`: Original extracted text
- `cleaned_text`: Normalized whitespace version
- `blocks`: List of BlockInfo objects
- `section_hints`: List of detected headings on page
- `has_tables`: Boolean flag
- `word_count`: Count of words in cleaned text

**DocumentExtraction**: Complete extraction result for entire PDF
- `document_id`: UUID for document (auto-generated if not provided)
- `source_file_name`: Original filename
- `source_file_path`: Full path to source file
- `total_pages`: Number of pages
- `extraction_timestamp`: ISO 8601 timestamp
- `pages`: List of PageExtraction objects
- `full_text`: Concatenated text from all pages
- `file_checksum`: MD5 hash for deduplication
- `total_word_count`: Total words across all pages

#### Main Methods

**`extract_document(pdf_path, document_id=None) -> DocumentExtraction`**
- Full extraction with all metadata
- Auto-generates UUID if not provided
- Analyzes blocks, detects headings, identifies tables
- Computes checksums for deduplication
- Recommended for new code

**`extract_text(pdf_path) -> str | None`**
- Legacy method: returns plain concatenated text
- Used for backward compatibility
- No metadata or structure analysis

**`extract_pages(pdf_path) -> list[PageExtraction]`**
- Extracts structured content for each page
- Useful for page-by-page processing

**`chunk_text(text) -> list[dict]`**
- Legacy word-based chunking
- Returns list of dicts with: text, index, token_count

**`extract_and_chunk(pdf_path) -> list[dict]`**
- Legacy: extract + chunk in one call
- Uses simple word-based chunking

**`extract_and_chunk_rich(pdf_path, document_id=None) -> (DocumentExtraction, list[ChunkRecord])`**
- Primary method for new code
- Returns both rich extraction and chunked records
- Integrates with DocumentChunker

#### Extraction Features

**Block-Level Analysis**
- Uses PyMuPDF `get_text("dict")` for structured extraction
- Extracts bounding boxes, font sizes, style information
- Distinguishes text blocks from tables/images

**Heading Detection**
- Bold text blocks are marked as headings
- Text with font size > median * 1.2 is marked as heading
- Headings become "section hints" for chunks

**Table Detection**
- Identifies table blocks from PDF structure
- Sets `has_tables` flag on PageExtraction
- Preserves table location information

**Whitespace Normalization**
- Collapses multiple spaces to single space
- Preserves paragraph breaks (double newlines)
- Removes excessive blank lines (>2 consecutive)

**File Integrity**
- Computes MD5 checksum of source file
- Enables deduplication in RAG pipeline

### 2. Document Chunker (`pdf_ingestion/chunker.py`)

#### ChunkRecord Dataclass

Represents a single chunk of text with metadata:
- `chunk_id`: Deterministic 16-char hex hash
- `document_id`: Parent document UUID
- `source_file_name`: Original filename
- `page_number`: Primary page number (1-indexed)
- `page_range`: List of all pages spanned by chunk
- `chunk_index`: Sequential index within document
- `section_hint`: Heading/section context (first 100 chars)
- `raw_text`: Original extracted text
- `cleaned_text`: Lowercase, normalized for indexing
- `token_count_estimate`: Approximate token count (char_count / 4)
- `char_count`: Exact character count
- `has_table_content`: Boolean flag

#### DocumentChunker Class

**`__init__(chunk_size=800, chunk_overlap=150, min_chunk_size=100)`**
- `chunk_size`: Target characters per chunk
- `chunk_overlap`: Characters to overlap between chunks
- `min_chunk_size`: Minimum size before merge with neighbor

**`chunk_document(doc: DocumentExtraction) -> list[ChunkRecord]`**
- Main entry point
- Processes each page independently
- Returns list of ChunkRecord objects in document order

**`generate_chunk_id(document_id, page_number, chunk_index) -> str`**
- Deterministic ID generation
- Hash: SHA256 of "document_id:page:index", first 16 hex chars
- Reproducible across runs (same input = same ID)

**`generate_preview(text, max_length=200) -> str`**
- Creates truncated preview
- Respects word boundaries
- Appends "..." if truncated

#### Chunking Strategy

1. **Per-Page Processing**: Each page is chunked independently
2. **Paragraph Splitting**: Text is split by double newlines
3. **Semantic Accumulation**: Paragraphs are accumulated until hitting `chunk_size`
4. **Heading Breaks**: When a heading is encountered, start new chunk
5. **Overlap Addition**: Previous chunk's tail is added to next chunk
6. **Size Filtering**: Chunks below `min_chunk_size` are merged with next chunk

#### Heading Detection

A paragraph is considered a heading if:
- It matches detected section hints exactly
- It's <80 characters AND contains a section hint
- It contains >60% uppercase words (max 5 words)

#### Text Cleaning

For indexing:
- Convert to lowercase
- Normalize whitespace
- Preserve alphanumeric and basic punctuation

## Usage Examples

### Basic Extraction

```python
from app.services.pdf_service import pdf_service

# Extract with metadata
doc_extraction = pdf_service.extract_document("/path/to/paper.pdf")
print(f"Document: {doc_extraction.document_id}")
print(f"Pages: {doc_extraction.total_pages}")
print(f"Words: {doc_extraction.total_word_count}")

# Legacy: plain text
text = pdf_service.extract_text("/path/to/paper.pdf")
```

### Full Extraction + Chunking (Recommended)

```python
from app.services.pdf_service import pdf_service

doc, chunks = pdf_service.extract_and_chunk_rich("/path/to/paper.pdf")

for chunk in chunks:
    print(f"Chunk {chunk.chunk_id}: page {chunk.page_number}, {chunk.char_count} chars")
    print(f"  Section: {chunk.section_hint}")
    print(f"  Text: {chunk.cleaned_text[:100]}...")
```

### Manual Chunking

```python
from app.services.pdf_service import pdf_service
from app.services.pdf_ingestion import DocumentChunker

# Extract document structure
doc = pdf_service.extract_document("/path/to/paper.pdf")

# Chunk with custom parameters
chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
chunks = chunker.chunk_document(doc)

# Store or embed chunks
for chunk in chunks:
    store_in_vector_db(
        chunk_id=chunk.chunk_id,
        text=chunk.cleaned_text,
        metadata={
            "document_id": chunk.document_id,
            "page": chunk.page_number,
            "section": chunk.section_hint,
        }
    )
```

### Page-by-Page Processing

```python
from app.services.pdf_service import pdf_service

pages = pdf_service.extract_pages("/path/to/paper.pdf")

for page in pages:
    print(f"Page {page.page_number}:")
    print(f"  Blocks: {len(page.blocks)}")
    print(f"  Section hints: {page.section_hints}")
    print(f"  Has tables: {page.has_tables}")
    for block in page.blocks:
        print(f"    {block.block_type}: {block.text[:50]}")
```

## Backward Compatibility

The implementation maintains full backward compatibility with existing code:

```python
# These legacy methods still work exactly as before
chunks = pdf_service.chunk_text(text)
chunks = pdf_service.extract_and_chunk("/path/to/paper.pdf")
text = pdf_service.extract_text("/path/to/paper.pdf")
```

## Configuration

Default parameters in `PDFService.__init__`:
- `chunk_size=1000`: Target characters per chunk
- `chunk_overlap=200`: Overlap between chunks

Default parameters in `DocumentChunker.__init__`:
- `chunk_size=800`: Target characters per chunk
- `chunk_overlap=150`: Overlap between chunks
- `min_chunk_size=100`: Minimum chunk size before merge

These can be customized per instance:

```python
service = PDFService(chunk_size=1500, chunk_overlap=300)
chunker = DocumentChunker(chunk_size=600, chunk_overlap=100, min_chunk_size=50)
```

## Performance Considerations

- **Block-level extraction** is more computationally expensive than plain text extraction (~2-3x)
- **Heading detection** uses median font size calculation (O(n) per page)
- **Chunking** is O(n) where n is total text length
- **Checksum computation** reads entire file (can be slow for large PDFs)

Typical performance:
- 10-page PDF: ~50-100ms extraction, ~10-20ms chunking
- 100-page PDF: ~500-1000ms extraction, ~100-200ms chunking

## Integration with RAG Pipeline

The DocumentChunker output integrates seamlessly with RAG:

```python
from app.services.pdf_service import pdf_service
from app.ai.embeddings import embed_text

doc, chunks = pdf_service.extract_and_chunk_rich(pdf_path)

# Embed and store
for chunk in chunks:
    embedding = embed_text(chunk.cleaned_text)

    # Store in vector DB with metadata
    vector_store.add(
        id=chunk.chunk_id,
        vector=embedding,
        text=chunk.raw_text,
        metadata={
            "document_id": chunk.document_id,
            "page": chunk.page_number,
            "section": chunk.section_hint,
            "source": chunk.source_file_name,
        }
    )
```

## Testing

Run the test suite:

```bash
cd backend
python3 test_pdf_service.py
```

This validates:
- All dataclass structures
- Method signatures and existence
- Deterministic chunk ID generation
- Synthetic document chunking
- Backward compatibility

## Error Handling

All methods include comprehensive error handling:

```python
try:
    doc = pdf_service.extract_document("/path/to/paper.pdf")
except FileNotFoundError:
    print("PDF not found")
except Exception as e:
    logger.error(f"Extraction failed: {e}", exc_info=True)
```

Errors are logged to Python logger with:
- Error messages
- Full stack traces (exc_info=True)
- Context (file path, document ID)

## Future Enhancements

Potential improvements for future releases:

1. **OCR Support**: Detect scanned PDFs and extract text via OCR
2. **Formula Preservation**: Better handling of equations and mathematical notation
3. **Reference Extraction**: Identify and extract bibliographic references
4. **Cross-Page Chunks**: Optional spanning of chunks across page boundaries
5. **Custom Block Types**: Extension mechanism for application-specific block classification
6. **Incremental Extraction**: Process only pages changed since last extraction
7. **Async Processing**: Async extraction for large document batches
8. **Caching**: LRU cache of extraction results based on file checksum

## Troubleshooting

**Issue**: Chunks are too small or too large
- **Solution**: Adjust `chunk_size` and `chunk_overlap` parameters

**Issue**: Headings not being detected
- **Solution**: Check `page.section_hints` to see what was detected
- Verify that bold text or large fonts are actually in the PDF
- Use `page.blocks` to inspect block-level metadata

**Issue**: Tables are not preserved
- **Solution**: Check `page.has_tables` flag
- Examine block-level analysis in `page.blocks`
- Note: Current implementation marks tables but doesn't extract their structure

**Issue**: Performance is slow
- **Solution**: Check if checksums need to be computed (disable if not needed)
- Profile with larger PDFs to identify bottlenecks
- Consider parallelizing extraction across pages

## Dependencies

- `PyMuPDF==1.25.3`: PDF parsing and extraction
- `Python>=3.9`: Type hints (dataclass, Optional, etc.)

All dependencies are in `backend/requirements.txt`.
