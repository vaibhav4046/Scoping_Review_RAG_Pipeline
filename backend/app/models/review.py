"""Review project model."""

from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    search_query: Mapped[str] = mapped_column(Text, nullable=True)
    inclusion_criteria: Mapped[str] = mapped_column(Text, nullable=True)
    exclusion_criteria: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="created",
        comment="created|searching|screening|extracting|validating|completed",
    )
    total_studies: Mapped[int] = mapped_column(Integer, default=0)

    # Foreign keys
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="reviews", lazy="selectin")
    studies = relationship("Study", back_populates="review", lazy="selectin", cascade="all, delete-orphan")
    task_logs = relationship("TaskLog", back_populates="review", lazy="selectin", cascade="all, delete-orphan")
