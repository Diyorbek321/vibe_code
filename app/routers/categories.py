import uuid

from fastapi import APIRouter, status

from app.core.deps import CompanyID, DB
from app.schemas.category import CategoryCreate, CategoryOut
from app.services import categories as cat_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(company_id: CompanyID, db: DB) -> list[CategoryOut]:
    return await cat_service.list_categories(company_id, db)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate, company_id: CompanyID, db: DB
) -> CategoryOut:
    return await cat_service.create_category(company_id, data, db)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID, company_id: CompanyID, db: DB
) -> None:
    await cat_service.delete_category(company_id, category_id, db)
