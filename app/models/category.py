import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # income | expense — used for validation in NLP extraction
    type: Mapped[str] = mapped_column(
        Enum("income", "expense", name="category_type_enum"), nullable=False
    )
    # Default seed categories cannot be deleted by users
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    company: Mapped["Company"] = relationship("Company", back_populates="categories")  # noqa: F821
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="category")  # noqa: F821
    budgets: Mapped[list["Budget"]] = relationship("Budget", back_populates="category")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name!r} type={self.type}>"
