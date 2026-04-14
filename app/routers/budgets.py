import uuid

from fastapi import APIRouter, status

from app.core.deps import CompanyID, DB
from app.schemas.budget import BudgetCreate, BudgetOut, BudgetStatus
from app.services import budgets as budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.post("", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
async def create_budget(
    data: BudgetCreate, company_id: CompanyID, db: DB
) -> BudgetOut:
    return await budget_service.create_budget(company_id, data, db)


@router.get("", response_model=list[BudgetOut])
async def list_budgets(company_id: CompanyID, db: DB) -> list[BudgetOut]:
    return await budget_service.list_budgets(company_id, db)


@router.get("/{budget_id}/status", response_model=BudgetStatus)
async def budget_status(
    budget_id: uuid.UUID, company_id: CompanyID, db: DB
) -> BudgetStatus:
    """Real-time spend vs limit for a single budget."""
    return await budget_service.get_budget_status(company_id, budget_id, db)
