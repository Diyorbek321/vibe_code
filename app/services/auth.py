"""
Auth service — user registration (with company creation) and login.
"""
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import settings
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserOut
from app.services.categories import seed_default_categories

logger = logging.getLogger(__name__)


async def register_user(data: UserCreate, db: AsyncSession) -> UserOut:
    """
    Create a new company + owner user in a single transaction.
    Seeds default categories for the new company.
    """
    # Guard against duplicate emails
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # 1. Create company
    company = Company(name=data.company_name)
    db.add(company)
    await db.flush()  # populate company.id without committing yet

    # 2. Create user
    user = User(
        company_id=company.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()

    # 3. Seed default categories for the new company
    await seed_default_categories(company.id, db)

    logger.info("Registered company=%s user=%s", company.id, user.id)
    return UserOut.model_validate(user)


async def login_user(email: str, password: str, db: AsyncSession) -> TokenResponse:
    """Verify credentials and return a signed JWT."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # <<< INTEGRATION: include profile fields so frontend can skip GET /me >>>
    token = create_access_token(
        data={
            "sub": str(user.id),
            "company_id": str(user.company_id),
            "email": user.email,
            "full_name": user.full_name,
        }
    )
    expire_secs = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    logger.info("User %s logged in", user.id)
    return TokenResponse(access_token=token, expires_in=expire_secs)
