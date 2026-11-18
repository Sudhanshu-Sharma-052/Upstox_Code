from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from database.database import SessionLocal
from schemas.account_funds_payments_schemas import (
    BrokerageRequest,
    MarginRequest,
    PayoutRequest,
    ModifyPayoutRequest,
    CancelPayoutRequest  
)
from services.account_funds_payments_service import (
    AccountFundsPaymentsService
)

router = APIRouter(
    prefix="/api/upstox",
    tags=["Account & Funds Payments"]
)

def get_db():

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get("/payins/{upstox_user_id}")
def get_payins(
    upstox_user_id: str,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .get_payins(
            db,
            upstox_user_id
        )
    )
    
    
@router.get(
    "/payouts/{upstox_user_id}"
)
def get_payouts(
    upstox_user_id: str,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .get_payouts(
            db=db,
            upstox_user_id=upstox_user_id
        )
    )  
    
    
@router.get(
    "/payout-modes/{upstox_user_id}"
)
def get_payout_modes(
    upstox_user_id: str,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .get_payout_modes(
            db=db,
            upstox_user_id=upstox_user_id
        )
    )      
    
    
@router.post(
    "/payout/{upstox_user_id}"
)
def payout_request(
    upstox_user_id: str,
    payload: PayoutRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .payout_request(
            db=db,
            upstox_user_id=upstox_user_id,
            mode=payload.mode,
            amount=payload.amount
        )
    )    
    
    
@router.put(
    "/payout/{upstox_user_id}/{transaction_id}"
)
def modify_payout(
    upstox_user_id: str,
    transaction_id: str,
    payload: ModifyPayoutRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .modify_payout(
            db=db,
            upstox_user_id=upstox_user_id,
            transaction_id=transaction_id,
            amount=payload.amount
        )
    )    
    
    
@router.delete(
    "/payout/{transaction_id}"
)
def cancel_payout(
    transaction_id: str,
    request: CancelPayoutRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .cancel_payout(
            db=db,
            upstox_user_id=request.upstox_user_id,
            transaction_id=transaction_id
        )
    )
    

@router.post(
    "/brokerage"
)
def get_brokerage(
    request: BrokerageRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .get_brokerage(
            db=db,
            upstox_user_id=request.upstox_user_id,
            instrument_token=request.instrument_token,
            quantity=request.quantity,
            product=request.product,
            transaction_type=request.transaction_type,
            price=request.price
        )
    ) 
    
    
@router.post(
    "/margin"
)
def get_margin(
    request: MarginRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsPaymentsService
        .get_margin(
            db=db,
            upstox_user_id=request.upstox_user_id,
            instruments=[
                instrument.model_dump(
                    exclude_none=True
                )
                for instrument
                in request.instruments
            ]
        )
    )       