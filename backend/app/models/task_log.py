"""Celery task tracking model."""

from typing import Optional

from sqlalchemy import String, Text, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaskLog(Base):
    __tablename__ = "task_logs"

    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="search|screening|extraction|validation",
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="pending",
        comment="pending|running|completed|failed",
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    review = relationship("Review", back_populates="task_logs")
