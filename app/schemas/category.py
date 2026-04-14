import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: Literal["income", "expense"]


class CategoryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    type: str
    is_default: bool
    created_at: datetime
