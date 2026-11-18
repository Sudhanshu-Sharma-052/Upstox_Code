from fastapi import APIRouter, Depends,Query
from sqlalchemy.orm import Session
from database.dependencies import get_db
from schemas.order_trading_schemas import(
    PlaceOrderRequest,
    MultiOrderRequest,
    ModifyOrderRequest,
)
from services.order_trading_service import OrderTradingService

router = APIRouter(
    prefix="/api/upstox/orders",
    tags=["Order Trading"],
)


@router.post("/place/{upstox_user_id}")
async def place_order(
    upstox_user_id: str,
    order: PlaceOrderRequest,
    db: Session = Depends(get_db),
):

    return await OrderTradingService.place_order(
        upstox_user_id=upstox_user_id,
        order=order,
        db=db,
    )
    
    
@router.post("/multi/place/{upstox_user_id}")
async def place_multi_order(
    upstox_user_id: str,
    request: MultiOrderRequest,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.place_multi_order(
        upstox_user_id=upstox_user_id,
        request=request,
        db=db,
    )
    
    
@router.put("/orders/modify/{upstox_user_id}")
async def modify_order(
    upstox_user_id: str,
    request: ModifyOrderRequest,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.modify_order(
        upstox_user_id=upstox_user_id,
        request=request,
        db=db,
    )
    
    
@router.delete("/orders/cancel/{upstox_user_id}/{order_id}")
async def cancel_order(
    upstox_user_id: str,
    order_id: str,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.cancel_order(
        upstox_user_id=upstox_user_id,
        order_id=order_id,
        db=db,
    )
    
    
@router.delete("/orders/multi/cancel/{upstox_user_id}")
async def cancel_multi_order(
    upstox_user_id: str,
    segment: str = None,
    tag: str = None,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.cancel_multi_order(
        upstox_user_id=upstox_user_id,
        db=db,
        segment=segment,
        tag=tag,
    )   
    
    
@router.post("/orders/positions/exit/{upstox_user_id}")
async def exit_all_positions(
    upstox_user_id: str,
    segment: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return await OrderTradingService.exit_all_positions(
        upstox_user_id=upstox_user_id,
        db=db,
        segment=segment,
        tag=tag,
    )   
    
    
@router.get("/orders/details/{upstox_user_id}/{order_id}")
async def get_order_details(
    upstox_user_id: str,
    order_id: str,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.get_order_details(
        upstox_user_id=upstox_user_id,
        order_id=order_id,
        db=db,
    )
  
  
@router.get("/orders/history/{upstox_user_id}")
async def get_order_history(
    upstox_user_id: str,
    order_id: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.get_order_history(
        upstox_user_id=upstox_user_id,
        db=db,
        order_id=order_id,
        tag=tag,
    )
    
    
@router.get("/orders/order-book/{upstox_user_id}")
async def get_order_book(
    upstox_user_id: str,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.get_order_book(
        upstox_user_id=upstox_user_id,
        db=db,
    )
    
    
@router.get("/trades/get-trades-for-day/{upstox_user_id}")
async def get_trades_for_day(
    upstox_user_id: str,
    db: Session = Depends(get_db),
):
    return await OrderTradingService.get_trades_for_day(
        upstox_user_id=upstox_user_id,
        db=db,
    )
    

@router.get("/order-trades/{upstox_user_id}/{order_id}")
async def get_order_trades(
    upstox_user_id: str,
    order_id: str,
    db: Session = Depends(get_db),
):
    """
    Get executed trades for a specific Upstox order.
    """

    return await OrderTradingService.get_order_trades(
        upstox_user_id=upstox_user_id,
        order_id=order_id,
        db=db,
    )
  

@router.get("/trade-history/{upstox_user_id}")
async def get_trade_history(
    upstox_user_id: str,
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    page_number: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=5000),
    segment: str | None = Query(
        None,
        description="Optional: EQ, FO, COM, CD, MF",
    ),
    db: Session = Depends(get_db),
):
    return await OrderTradingService.get_trade_history(
        upstox_user_id=upstox_user_id,
        start_date=start_date,
        end_date=end_date,
        page_number=page_number,
        page_size=page_size,
        segment=segment,
        db=db,
    )
