"""Screening decision model."""

from typing import Optional

from sqlalchemy import String, Text, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Screening(Base):
    __tablename__ = "screenings"

    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="include|exclude|uncertain",
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    study = relationship("Study", back_populates="screenings")
