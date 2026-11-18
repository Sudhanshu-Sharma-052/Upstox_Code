
import logging

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
)

from pydantic import ValidationError
from sqlalchemy.orm import Session

from database.dependencies import get_db

from schemas.websocket_market_data_schemas import (
    MarketDataSubscriptionRequest,
)

from services.websocket_market_data_service import (
    WebsocketMarketDataService,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/upstox/market-data",
    tags=["WebSocket Market Data"],
)


# --------------------------------------------------
# WEBSOCKET Connection 
# --------------------------------------------------


@router.websocket("/feed/{upstox_user_id}")
async def market_data_feed(
    websocket: WebSocket,
    upstox_user_id: str,
    db: Session = Depends(get_db),
):

    await websocket.accept()

    try:

        raw_request = await websocket.receive_json()

        subscription = (
            MarketDataSubscriptionRequest.model_validate(
                raw_request
            )
        )

        await WebsocketMarketDataService.connect_market_data(
            websocket=websocket,
            upstox_user_id=upstox_user_id,
            subscription=subscription,
            db=db,
        )

    except WebSocketDisconnect:

        logger.info(
            "Frontend disconnected for user %s",
            upstox_user_id,
        )

    except (ValidationError, ValueError) as exc:

        try:
            await websocket.send_json({
                "success": False,
                "message": "Invalid market data request",
                "detail": str(exc),
            })

            await websocket.close(code=1008)

        except Exception:
            pass

    except Exception:

        logger.exception(
            "Market data route failed for user %s",
            upstox_user_id,
        )

        try:
            await websocket.send_json({
                "success": False,
                "message": "Market data connection failed",
            })

            await websocket.close(code=1011)

        except Exception:
            pass


# --------------------------------------------------
# POST: Validate Market Data Subscription
# --------------------------------------------------

# @router.post("/subscription/{upstox_user_id}")
# def validate_market_data_subscription(
#     upstox_user_id: str,
#     request: MarketDataSubscriptionRequest,
#     db: Session = Depends(get_db),
# ):
#
#     try:
#
#         WebsocketMarketDataService.get_access_token(
#             upstox_user_id=upstox_user_id,
#             db=db,
#         )
#
#         return {
#             "success": True,
#             "message": "Market data subscription validated successfully",
#             "upstox_user_id": upstox_user_id,
#             "subscription": request.model_dump(),
#             "websocket_endpoint": (
#                 f"/api/upstox/market-data/feed/{upstox_user_id}"
#             ),
#         }
#
#     except ValueError as exc:
#
#         raise HTTPException(
#             status_code=404,
#             detail=str(exc),
#         )
#


# # --------------------------------------------------
# # GET: Market Data Authorized URL
# # --------------------------------------------------
#
# @router.get("/authorize/{upstox_user_id}")
# async def get_market_data_authorized_url(
#     upstox_user_id: str,
#     db: Session = Depends(get_db),
# ):
#
#     try:
#
#         access_token = (
#             WebsocketMarketDataService.get_access_token(
#                 upstox_user_id=upstox_user_id,
#                 db=db,
#             )
#         )
#
#         authorized_url = (
#             await WebsocketMarketDataService
#             .get_authorized_websocket_url(
#                 access_token=access_token,
#             )
#         )
#
#         return {
#             "success": True,
#             "message": "Market Data Feed authorized successfully",
#             "upstox_user_id": upstox_user_id,
#             "authorized_redirect_uri": authorized_url,
#         }
#
#     except ValueError as exc:
#
#         raise HTTPException(
#             status_code=404,
#             detail=str(exc),
#         )
#
#     except Exception as exc:
#
#         logger.exception(
#             "Market data authorization failed for user %s",
#             upstox_user_id,
#         )
#
#         raise HTTPException(
#             status_code=502,
#             detail=str(exc),
#         )
#
#
#
# # --------------------------------------------------
# # WEBSOCKET: Portfolio Stream Feed
# # --------------------------------------------------
#
# @router.websocket("/portfolio-feed/{upstox_user_id}")
# async def portfolio_stream_feed(
#     websocket: WebSocket,
#     upstox_user_id: str,
#     db: Session = Depends(get_db),
#     update_types: str = "order",
# ):
#
#     await websocket.accept()
#
#     try:
#
#         await WebsocketMarketDataService.connect_portfolio_stream(
#             websocket=websocket,
#             upstox_user_id=upstox_user_id,
#             db=db,
#             update_types=update_types,
#         )
#
#     except WebSocketDisconnect:
#
#         logger.info(
#             "Frontend disconnected from Portfolio Stream for user %s",
#             upstox_user_id,
#         )
#
#     except Exception as exc:
#
#         logger.exception(
#             "Portfolio Stream failed for user %s",
#             upstox_user_id,
#         )
#
#         try:
#
#             await websocket.send_json({
#                 "success": False,
#                 "message": "Portfolio Stream connection failed",
#                 "detail": str(exc),
#             })
#
#             await websocket.close(code=1011)
#
#         except Exception:
#             pass
