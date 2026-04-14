import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )

    # First day of the budget month, e.g. 2024-11-01
    month: Mapped[date] = mapped_column(Date, nullable=False)

    # Maximum spend allowed for this category in this month
    limit_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    # Fraction of limit_amount at which alerts fire (default 80 %)
    alert_threshold: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)

    # Track whether the threshold alert was already sent this month
    alert_sent: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    company: Mapped["Company"] = relationship("Company", back_populates="budgets")  # noqa: F821
    category: Mapped["Category"] = relationship("Category", back_populates="budgets")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Budget id={self.id} category_id={self.category_id} "
            f"month={self.month} limit={self.limit_amount}>"
        )
