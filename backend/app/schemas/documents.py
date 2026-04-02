"""Document content and evidence package schemas."""
from pydantic import BaseModel, Field


class DocumentPageContent(BaseModel):
    """Content of a single page."""
    page_number: int
    text: str
    section_hints: list[str] = Field(default_factory=list)
    has_tables: bool = False
    word_count: int = 0


class DocumentContent(BaseModel):
    """Full document content with page breakdown."""
    document_id: str
    source_file_name: str
    total_pages: int
    pages: list[DocumentPageContent]
    total_word_count: int


class EvidencePackage(BaseModel):
    """Evidence package for validation - links extracted value to source text."""
    extracted_value: str
    field_name: str
    source_chunks: list[dict] = Field(default_factory=list, description="ChunkResult-like dicts")
    page_references: list[int] = Field(default_factory=list)
    confidence_note: str = ""
