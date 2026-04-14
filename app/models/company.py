import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Telegram chat_id for sending budget alerts (can be a group or user)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships (back-populated) ────────────────────────────────────────
    users: Mapped[list["User"]] = relationship("User", back_populates="company")  # noqa: F821
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="company")  # noqa: F821
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="company")  # noqa: F821
    budgets: Mapped[list["Budget"]] = relationship("Budget", back_populates="company")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"
