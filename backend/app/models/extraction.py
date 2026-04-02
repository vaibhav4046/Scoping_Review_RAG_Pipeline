"""PICO extraction model."""

from typing import Optional

from sqlalchemy import String, Text, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Extraction(Base):
    __tablename__ = "extractions"

    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False, index=True)

    # PICO fields
    population: Mapped[str] = mapped_column(Text, default="Not Reported")
    intervention: Mapped[str] = mapped_column(Text, default="Not Reported")
    comparator: Mapped[str] = mapped_column(Text, default="Not Reported")
    outcome: Mapped[str] = mapped_column(Text, default="Not Reported")
    study_design: Mapped[str] = mapped_column(Text, default="Not Reported")
    sample_size: Mapped[str] = mapped_column(String(100), default="Not Reported")
    duration: Mapped[str] = mapped_column(String(256), default="Not Reported")
    setting: Mapped[str] = mapped_column(Text, default="Not Reported")

    # Confidence scores per field (JSON: {"population": 0.95, ...})
    confidence_scores: Mapped[dict] = mapped_column(JSON, default=dict)

    # Source quotes grounding each extraction (JSON: {"population": "quote from text..."})
    source_quotes: Mapped[dict] = mapped_column(JSON, default=dict)

    # Model info
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    study = relationship("Study", back_populates="extractions")
    validations = relationship("Validation", back_populates="extraction", cascade="all, delete-orphan")
