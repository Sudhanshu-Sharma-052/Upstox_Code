from fastapi import APIRouter, Depends, HTTPException,Query
from sqlalchemy.orm import Session
from database.dependencies import get_db
from schemas.gtt_order_schemas import GTTModifySchema, GTTOrderSchema,GTTCancelSchema
from services.gtt_order_service import GTTOrderService

router = APIRouter(
    prefix="/api/gtt",
    tags=["GTT Orders"],
)


@router.post("/place/{upstox_user_id}")
def place_gtt_order(
    upstox_user_id: str,
    order: GTTOrderSchema,
    db: Session = Depends(get_db),
):
    result = GTTOrderService.place_gtt_order(
        upstox_user_id=upstox_user_id,
        db=db,
        order=order,
    )

    if result["status"] == "error":
        raise HTTPException(
            status_code=400,
            detail=result,
        )

    if result["status"] == "failed":
        raise HTTPException(
            status_code=result["upstox_http_status"],
            detail=result,
        )

    return result


@router.put("/modify/{upstox_user_id}")
def modify_gtt_order(
    upstox_user_id: str,
    order: GTTModifySchema,
    db: Session = Depends(get_db),
):
    result = GTTOrderService.modify_gtt_order(
        upstox_user_id=upstox_user_id,
        db=db,
        order=order,
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=400,
            detail=result,
        )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=result.get("upstox_http_status", 400),
            detail=result,
        )

    return result


@router.delete("/cancel/{upstox_user_id}")
def cancel_gtt_order(
    upstox_user_id: str,
    order: GTTCancelSchema,
    db: Session = Depends(get_db),
):
    result = GTTOrderService.cancel_gtt_order(
        upstox_user_id=upstox_user_id,
        db=db,
        order=order,
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=400,
            detail=result,
        )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=result.get("upstox_http_status", 400),
            detail=result,
        )
        
    return result


@router.get("/details/{upstox_user_id}")
def get_gtt_order_details(
    upstox_user_id: str,
    gtt_order_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    result = GTTOrderService.get_gtt_order_details(
        upstox_user_id=upstox_user_id,
        db=db,
        gtt_order_id=gtt_order_id,
    )

    if result.get("status") == "error":
        message = result.get("message", "")

        status_code = (
            404 if "not found" in message.lower() else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=result,
        )

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=result.get("upstox_http_status", 400),
            detail=result,
        )

    return result