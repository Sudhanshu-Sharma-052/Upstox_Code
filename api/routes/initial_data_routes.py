from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.dependencies import get_db
from services.initial_data_service import InitialDataService


router = APIRouter(
    prefix="/api/upstox",
    tags=["Initial Data"],
)


@router.get("/initial-data/{upstox_user_id}")
async def get_initial_data(
    upstox_user_id: str,
    db: Session = Depends(get_db),
):

    service = InitialDataService(db)

    return await service.get_initial_data(
        upstox_user_id
    )