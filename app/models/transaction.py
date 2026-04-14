import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    type: Mapped[str] = mapped_column(
        Enum("income", "expense", name="transaction_type_enum"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source tells us where the entry originated — used for UX and audit
    source: Mapped[str] = mapped_column(
        Enum("telegram", "web", name="transaction_source_enum"),
        nullable=False,
        default="web",
    )

    # The actual date of the transaction (may differ from created_at)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Soft delete — records are never physically removed
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Optimistic concurrency lock — incremented on every UPDATE
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    company: Mapped["Company"] = relationship("Company", back_populates="transactions")  # noqa: F821
    user: Mapped["User"] = relationship("User", back_populates="transactions")  # noqa: F821
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} type={self.type} "
            f"amount={self.amount} date={self.date}>"
        )
