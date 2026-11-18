from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.dependencies import get_db
from services.index_data_service import IndexDataService
from services.websocket_market_data_service import (
    WebsocketMarketDataService,
)


router = APIRouter(
    prefix="/api/upstox/index-data",
    tags=["Index Live Data"],
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DASHBOARD_FILE = (
    PROJECT_ROOT / "templates" / "index_dashboard.html"
)


@router.get("/dashboard/{upstox_user_id}")
def index_dashboard(
    upstox_user_id: str,
    db: Session = Depends(get_db),
):
    try:
        if upstox_user_id == "current":
            upstox_user_id = (
                WebsocketMarketDataService
                .get_latest_access_token_user_id(db)
            )

        # Check whether the user has a saved Upstox access token
        access_token = WebsocketMarketDataService.get_access_token(
            upstox_user_id,
            db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Upstox login required.",
        )

    if not DASHBOARD_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Index dashboard HTML file not found.",
        )

    return FileResponse(
        path=str(DASHBOARD_FILE),
        media_type="text/html",
    )


@router.websocket("/feed/{upstox_user_id}")
async def index_data_websocket(
    websocket: WebSocket,
    upstox_user_id: str,
    db: Session = Depends(get_db),
):
    await IndexDataService.stream_indices(
        websocket=websocket,
        upstox_user_id=upstox_user_id,
        db=db,
    )
