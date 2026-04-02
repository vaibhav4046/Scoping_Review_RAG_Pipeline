"""Cross-LLM validation model."""

from sqlalchemy import String, Text, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Validation(Base):
    __tablename__ = "validations"

    extraction_id: Mapped[str] = mapped_column(ForeignKey("extractions.id"), nullable=False, index=True)

    # Validator model info
    validator_model: Mapped[str] = mapped_column(String(100), nullable=False)
    validator_provider: Mapped[str] = mapped_column(String(50), nullable=False)

    # Validation results
    agreement_score: Mapped[float] = mapped_column(Float, nullable=False)
    field_agreements: Mapped[dict] = mapped_column(
        JSON, default=dict,
        comment='{"population": true, "intervention": false, ...}',
    )
    discrepancies: Mapped[dict] = mapped_column(
        JSON, default=dict,
        comment='{"intervention": {"original": "...", "validator": "...", "resolved": "..."}}',
    )
    validator_extractions: Mapped[dict] = mapped_column(JSON, default=dict)

    # Final
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    human_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    final_decision: Mapped[str] = mapped_column(String(50), default="pending")

    # Relationships
    extraction = relationship("Extraction", back_populates="validations")
