"""Study (article/paper) model."""

from typing import Optional

from sqlalchemy import String, Text, ForeignKey, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Study(Base):
    __tablename__ = "studies"

    # Identifiers
    pmid: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    pmcid: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Metadata
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    journal: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    publication_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mesh_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # PDF info
    pdf_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    pdf_available: Mapped[bool] = mapped_column(default=False)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pipeline status
    screening_status: Mapped[str] = mapped_column(String(30), default="pending")
    extraction_status: Mapped[str] = mapped_column(String(30), default="pending")
    validation_status: Mapped[str] = mapped_column(String(30), default="pending")

    # Foreign keys
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), nullable=False)

    # Relationships
    review = relationship("Review", back_populates="studies")
    embeddings = relationship("Embedding", back_populates="study", cascade="all, delete-orphan")
    screenings = relationship("Screening", back_populates="study", cascade="all, delete-orphan")
    extractions = relationship("Extraction", back_populates="study", cascade="all, delete-orphan")
