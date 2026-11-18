from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.dependencies import get_db
from schemas.ipo_orders_schemas import IPOListQuerySchema
from services.ipo_orders_service import IPOOrdersService

router = APIRouter(
    prefix="/api/ipo",
    tags=["IPO Orders"],
)


@router.get("/list")
def get_ipos(
    upstox_user_id: str,
    query: IPOListQuerySchema = Depends(),
    db: Session = Depends(get_db),
):
    result = IPOOrdersService.get_ipos(
        upstox_user_id=upstox_user_id,
        db=db,
        status=query.status,
        issue_type=query.issue_type,
        page_number=query.page_number,
        records=query.records,
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=401,
            detail=result,
        )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=result.get("upstox_http_status", 502),
            detail=result,
        )

    return result
