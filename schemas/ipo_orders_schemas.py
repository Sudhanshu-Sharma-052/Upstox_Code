from typing import Literal, Optional
from pydantic import BaseModel, Field


class IPOListQuerySchema(BaseModel):
    status: Literal["open", "closed", "listed", "upcoming"] = "open"

    issue_type: Optional[Literal["regular", "sme"]] = None

    page_number: int = Field(default=1, ge=1)

    records: int = Field(default=20, ge=1, le=30)
