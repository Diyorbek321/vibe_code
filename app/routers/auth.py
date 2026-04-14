from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DB, CurrentUser
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: UserCreate, db: DB) -> UserOut:
    """
    Create a new company + owner account.
    Seeds default categories automatically.
    """
    return await auth_service.register_user(data, db)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: DB) -> TokenResponse:
    """Exchange email/password for a signed JWT."""
    return await auth_service.login_user(data.email, data.password, db)


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    """Return the authenticated user's profile."""
    return UserOut.model_validate(current_user)
