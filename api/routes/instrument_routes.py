from fastapi import (
    APIRouter,
    Depends
)
from sqlalchemy.orm import Session
from database.dependencies import get_db
from schemas.instrument_schema import (
     InstrumentSearchRequest
 )
from services.instrument_service import (
    InstrumentService
)

router = APIRouter(
    prefix="/api/upstox/instrument",
    tags=["Instruments"]
)


@router.get(
    "/sync"
)
def sync_instruments(

    db: Session = Depends(
        get_db
    )
):

    return (
        InstrumentService
        .sync_instruments(
            db
        )
    )


@router.post(
    "/search"
)
def search_instrument(

    request: InstrumentSearchRequest,

    db: Session = Depends(
        get_db
    )
):

    return InstrumentService.search_instrument(

        db=db,

        search=request.search
    )