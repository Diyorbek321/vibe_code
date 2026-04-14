"""
Category service — CRUD + default seeding.
Default categories are created once per company on registration.
"""
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryOut

logger = logging.getLogger(__name__)

# ── Default seed data ──────────────────────────────────────────────────────────
# Tuple: (name, type)
DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Savdo", "income"),
    ("Logistika", "expense"),
    ("Ijara", "expense"),
    ("Maosh", "expense"),
    ("Kommunal", "expense"),
    ("Marketing", "expense"),
    ("Soliq", "expense"),
    ("Boshqa", "expense"),
]


async def seed_default_categories(
    company_id: uuid.UUID, db: AsyncSession
) -> None:
    """Create the default category set for a newly created company."""
    for name, cat_type in DEFAULT_CATEGORIES:
        db.add(
            Category(
                company_id=company_id,
                name=name,
                type=cat_type,
                is_default=True,
            )
        )
    logger.debug("Seeded %d default categories for company %s", len(DEFAULT_CATEGORIES), company_id)


async def list_categories(
    company_id: uuid.UUID, db: AsyncSession
) -> list[CategoryOut]:
    result = await db.execute(
        select(Category)
        .where(Category.company_id == company_id)
        .order_by(Category.is_default.desc(), Category.name)
    )
    categories = result.scalars().all()
    return [CategoryOut.model_validate(c) for c in categories]


async def create_category(
    company_id: uuid.UUID, data: CategoryCreate, db: AsyncSession
) -> CategoryOut:
    # Prevent duplicates within the same company
    existing = await db.execute(
        select(Category).where(
            Category.company_id == company_id,
            Category.name == data.name,
            Category.type == data.type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{data.name}' ({data.type}) already exists",
        )
    cat = Category(company_id=company_id, name=data.name, type=data.type, is_default=False)
    db.add(cat)
    await db.flush()
    return CategoryOut.model_validate(cat)


async def delete_category(
    company_id: uuid.UUID, category_id: uuid.UUID, db: AsyncSession
) -> None:
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.company_id == company_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if cat.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Default categories cannot be deleted",
        )
    await db.delete(cat)


async def resolve_category_by_name(
    company_id: uuid.UUID, name: str, db: AsyncSession
) -> uuid.UUID | None:
    """
    Fuzzy-match a category name returned by the LLM to an existing DB category.
    Returns None if no match found (caller should assign to 'Boshqa').
    """
    result = await db.execute(
        select(Category).where(
            Category.company_id == company_id,
            Category.name.ilike(f"%{name}%"),
        )
    )
    cat = result.scalars().first()
    if cat:
        return cat.id

    # Fallback: return 'Boshqa'
    fallback = await db.execute(
        select(Category).where(
            Category.company_id == company_id,
            Category.name == "Boshqa",
        )
    )
    boshqa = fallback.scalar_one_or_none()
    return boshqa.id if boshqa else None
