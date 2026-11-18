from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from database.dependencies import get_db
from schemas.account_funds_user_schemas import (
    AccountFundsUserRequest,
    KillSwitchRequest,
    KillSwitchStatusRequest,
    StaticIPRequest,
    UpdateStaticIPRequest
)
from services.account_funds_user_service import (
    AccountFundsUserService
)

router = APIRouter(
    prefix="/api/upstox",
    tags=["Account & Funds User"]
)


@router.get("/profile/{upstox_user_id}")
def get_profile(
    upstox_user_id: str,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsUserService
        .get_profile(
            db,
            upstox_user_id
        )
    )


@router.post(
    "/funds-and-margin"
)
def get_funds_and_margin(
    request: AccountFundsUserRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsUserService
        .get_funds_and_margin(
            db=db,
            upstox_user_id=request.upstox_user_id
        )
    )
    
    
@router.post(
    "/kill-switch"
)
def update_kill_switch(
    request: KillSwitchRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsUserService
        .update_kill_switch(
            db=db,
            upstox_user_id=request.upstox_user_id,
            updates=request.updates
        )
    )  
    
    
@router.post(
    "/kill-switch-status"
)
def get_kill_switch_status(
    request: KillSwitchStatusRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsUserService
        .get_kill_switch_status(
            db=db,
            upstox_user_id=request.upstox_user_id
        )
    )      
    

@router.post(
    "/static-ip"
)
def get_static_ips(
    request: StaticIPRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsUserService
        .get_static_ips(
            db=db,
            upstox_user_id=request.upstox_user_id
        )
    )    
    
    
@router.put(
    "/static-ip"
)
def update_static_ips(
    request: UpdateStaticIPRequest,
    db: Session = Depends(get_db)
):

    return (
        AccountFundsUserService
        .update_static_ips(
            db=db,
            upstox_user_id=request.upstox_user_id,
            primary_ip=request.primary_ip,
            secondary_ip=request.secondary_ip
        )
    )    