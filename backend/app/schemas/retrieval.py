"""Retrieval and document processing schemas for the PDF/RAG pipeline."""
from pydantic import BaseModel, Field


class ChunkResult(BaseModel):
    """A single retrieved chunk with full provenance metadata."""
    chunk_id: str
    document_id: str
    source_file_name: str
    page_number: int
    page_range: list[int] = Field(default_factory=list)
    chunk_index: int
    chunk_text: str
    score: float = Field(ge=0.0, le=1.0, description="Relevance score (cosine similarity, 0-1)")
    section_hint: str | None = None
    preview: str | None = None
    has_table_content: bool = False

    model_config = {"from_attributes": True}


class RetrievalRequest(BaseModel):
    """Request to retrieve relevant chunks."""
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    document_id: str | None = None
    study_id: str | None = None
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RetrievalResponse(BaseModel):
    """Response from a retrieval query."""
    query: str
    results: list[ChunkResult]
    total_results: int
    retrieval_time_ms: float


class PICORetrievalResponse(BaseModel):
    """Specialized response for PICO extraction context."""
    study_id: str
    source_file_name: str | None = None
    context_chunks: list[ChunkResult]
    total_chunks_available: int
    pico_queries_used: list[str] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """Metadata about an ingested document."""
    document_id: str
    source_file_name: str
    source_file_path: str
    total_pages: int
    total_chunks: int
    total_word_count: int
    file_checksum: str
    extraction_timestamp: str
    ingestion_status: str = "completed"

    model_config = {"from_attributes": True}


class IngestRequest(BaseModel):
    """Request to ingest a PDF (by path or study_id)."""
    study_id: str | None = None
    pdf_path: str | None = None
    reindex: bool = False


class IngestResponse(BaseModel):
    """Response from PDF ingestion."""
    document_id: str
    source_file_name: str
    total_pages: int
    total_chunks: int
    chunks_indexed: int
    status: str = "completed"
    message: str = ""


class BulkIngestRequest(BaseModel):
    """Ingest multiple PDFs."""
    pdf_paths: list[str] = Field(default_factory=list)
    review_id: str | None = None
    reindex: bool = False


class BulkIngestResponse(BaseModel):
    """Response from bulk ingestion."""
    total_files: int
    successful: int
    failed: int
    results: list[IngestResponse]
    errors: list[dict] = Field(default_factory=list)


class DocumentChunkList(BaseModel):
    """List chunks for a document (for debugging/inspection)."""
    document_id: str
    source_file_name: str
    total_chunks: int
    chunks: list[ChunkResult]


class ReindexRequest(BaseModel):
    """Request to reindex documents."""
    study_ids: list[str] = Field(default_factory=list)
    force: bool = False
