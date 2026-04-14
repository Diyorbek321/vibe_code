"""
FastAPI dependency providers for authentication and company-scoped isolation.
Every protected route injects `current_user` and `company_id` via these deps.
"""
import uuid
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Decode JWT → load User from DB → return User.
    Raises HTTP 401 on any failure so individual routes never need to repeat this.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise credentials_exception from exc

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def get_company_id(
    current_user: Annotated[User, Depends(get_current_user)],
) -> uuid.UUID:
    """
    Convenience dep: returns the company_id from the authenticated user.
    Use this in all company-scoped queries to enforce row-level isolation.
    """
    return current_user.company_id


# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
CompanyID = Annotated[uuid.UUID, Depends(get_company_id)]
DB = Annotated[AsyncSession, Depends(get_db)]
