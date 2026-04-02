"""Vector embedding chunks for RAG."""

from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.config import get_settings

settings = get_settings()


class Embedding(Base):
    __tablename__ = "embeddings"

    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False, index=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding = mapped_column(Vector(settings.embedding_dimensions), nullable=False)

    # ── New metadata fields (Vaibhav's enhancement) ──
    document_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # JSON string like "[1,2]"
    chunk_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    section_hint: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    has_table_content: Mapped[bool] = mapped_column(Boolean, default=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    study = relationship("Study", back_populates="embeddings")
