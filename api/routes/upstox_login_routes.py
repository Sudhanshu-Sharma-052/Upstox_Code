from fastapi import APIRouter, Depends,Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database.dependencies import get_db
from schemas.upstox_login_schemas import (
    ForgotPasswordRequest,
    SignupRequest,
    UpstoxLoginRequest
)
from services.upstox_login_service import (
    UpstoxLoginService
)

router = APIRouter(
    prefix="/api/upstox",
    tags=["Upstox Signup & Login"]
)


@router.post("/signup")
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db)
):
    return UpstoxLoginService.signup(
        db=db,
        payload=payload
    )




@router.post("/authorize")
def authorize(
    payload: UpstoxLoginRequest,
    db: Session = Depends(get_db)
):
    return UpstoxLoginService.generate_login_url(
        db=db,
        upstox_user_id=payload.upstox_user_id,
        password=payload.password
    )


@router.get("/login/callback", include_in_schema=False)
def login_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):

    result = UpstoxLoginService.auth_callback(
        db=db,
        code=code,
        state=state,
    )

    if result.get("success"):

        return RedirectResponse(
            url="https://pro.upstox.com/",
            status_code=303,
        )

    return result


@router.post("/get-token/{upstox_user_id}")
def get_token(
    upstox_user_id: str,
    db: Session = Depends(get_db)
):
    return UpstoxLoginService.get_token(
        db=db,
        upstox_user_id=upstox_user_id
    )


@router.get("/request-token/{upstox_user_id}")
def request_token(
    upstox_user_id: str,
    db: Session = Depends(get_db)
):
    return UpstoxLoginService.request_token(
        db=db,
        upstox_user_id=upstox_user_id
    )
    
    
@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    return UpstoxLoginService.forgot_password(
        db=db,
        upstox_user_id=payload.upstox_user_id,
        email=payload.email,
        new_password=payload.new_password
    )


@router.delete(
    "/logout/{upstox_user_id}"
)
def logout(
    upstox_user_id: str,
    db: Session = Depends(get_db)
):

    return (
        UpstoxLoginService.logout(
            db=db,
            upstox_user_id=upstox_user_id
        )
    )
