"""
Transaction service — full CRUD with soft-delete and optimistic locking.
All queries are scoped to company_id to enforce data isolation.
"""
import logging
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionList,
    TransactionOut,
    TransactionUpdate,
)

logger = logging.getLogger(__name__)


async def create_transaction(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    data: TransactionCreate,
    db: AsyncSession,
) -> TransactionOut:
    tx = Transaction(
        company_id=company_id,
        user_id=user_id,
        category_id=data.category_id,
        amount=data.amount,
        type=data.type,
        description=data.description,
        source=data.source,
        date=data.date,
        version=1,
    )
    db.add(tx)
    await db.flush()  # get tx.id without committing
    logger.info("Transaction created: id=%s company=%s", tx.id, company_id)
    return TransactionOut.model_validate(tx)


async def get_transaction(
    company_id: uuid.UUID, tx_id: uuid.UUID, db: AsyncSession
) -> Transaction:
    """Retrieve a single non-deleted transaction or raise 404."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == tx_id,
            Transaction.company_id == company_id,
            Transaction.is_deleted == False,  # noqa: E712
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


async def list_transactions(
    company_id: uuid.UUID,
    db: AsyncSession,
    page: int = 1,
    limit: int = 50,
    type_filter: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> TransactionList:
    query = select(Transaction).where(
        Transaction.company_id == company_id,
        Transaction.is_deleted == False,  # noqa: E712
    )
    if type_filter:
        query = query.where(Transaction.type == type_filter)
    if date_from:
        query = query.where(Transaction.date >= date_from)
    if date_to:
        query = query.where(Transaction.date <= date_to)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    query = (
        query.order_by(Transaction.date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(query)
    items = [TransactionOut.model_validate(r) for r in result.scalars().all()]

    return TransactionList(items=items, total=total, page=page, limit=limit)


async def update_transaction(
    company_id: uuid.UUID,
    tx_id: uuid.UUID,
    data: TransactionUpdate,
    db: AsyncSession,
) -> TransactionOut:
    """
    Partial update with optimistic locking.
    Raises 409 if `data.version` doesn't match the current DB version.
    """
    tx = await get_transaction(company_id, tx_id, db)

    # ── Optimistic lock check ──────────────────────────────────────────────
    if tx.version != data.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Version conflict: expected {tx.version}, got {data.version}. "
                "Reload and retry."
            ),
        )

    # Apply only provided fields (PATCH semantics)
    if data.amount is not None:
        tx.amount = data.amount
    if data.type is not None:
        tx.type = data.type
    if data.category_id is not None:
        tx.category_id = data.category_id
    if data.description is not None:
        tx.description = data.description
    if data.date is not None:
        tx.date = data.date

    tx.version += 1  # increment lock version on every write
    await db.flush()
    # Refresh to pull server-generated fields (updated_at onupdate=func.now())
    await db.refresh(tx)
    logger.info("Transaction updated: id=%s version=%d", tx.id, tx.version)
    return TransactionOut.model_validate(tx)


async def soft_delete_transaction(
    company_id: uuid.UUID, tx_id: uuid.UUID, db: AsyncSession
) -> None:
    tx = await get_transaction(company_id, tx_id, db)
    tx.is_deleted = True
    tx.version += 1
    logger.info("Transaction soft-deleted: id=%s", tx.id)


async def get_last_transaction(
    company_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Transaction | None:
    """Return the most recent non-deleted transaction by this user."""
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.company_id == company_id,
            Transaction.user_id == user_id,
            Transaction.is_deleted == False,  # noqa: E712
        )
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
