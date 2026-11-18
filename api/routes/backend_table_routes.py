from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.dependencies import get_db
from schemas.backend_table_schema import BackendTableUpdate
from services.backend_table_service import BackendTableService


router = APIRouter(
    prefix="/api/upstox/backend-table",
    tags=["Backend Table"],
)


@router.get("/{user_id}")
def get_backend_config(
    user_id: str,
    db: Session = Depends(get_db),
):
    return BackendTableService.get_config(
        db=db,
        user_id=user_id,
    )


@router.put("/{user_id}")
def update_backend_config(
    user_id: str,
    updates: BackendTableUpdate,
    db: Session = Depends(get_db),
):
    return BackendTableService.update_config(
        db=db,
        user_id=user_id,
        updates=updates,
    )
