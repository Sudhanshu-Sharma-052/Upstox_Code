
import asyncio
import json
import logging
from datetime import datetime

import httpx
import upstox_client
import websockets

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from google.protobuf.json_format import MessageToDict

from config.websocket_market_data_config import (
    websocket_market_data_settings,
)

from models.upstox_user_login import AccessToken, IST

from schemas.websocket_market_data_schemas import (
    MarketDataSubscriptionRequest,
    PortfolioStreamRequest,
)

from upstox_client.feeder.proto import MarketDataFeedV3_pb2


logger = logging.getLogger(__name__)


class WebsocketMarketDataService:

    @staticmethod
    def get_latest_access_token_user_id(db: Session) -> str:
        now = datetime.now(IST).replace(tzinfo=None)
        token_record = (
            db.query(AccessToken)
            .filter(
                AccessToken.access_token.isnot(None),
                AccessToken.token_expiry_at > now,
            )
            .order_by(
                AccessToken.token_created_at.desc(),
                AccessToken.id.desc(),
            )
            .first()
        )

        if not token_record or not token_record.upstox_user_id:
            raise ValueError(
                "No valid Upstox access token found. Please login first."
            )

        return token_record.upstox_user_id

    @staticmethod
    def get_access_token(
        upstox_user_id: str,
        db: Session,
    ):
        token_record = (
            db.query(AccessToken)
            .filter(
                AccessToken.upstox_user_id == upstox_user_id
            )
            .order_by(AccessToken.id.desc())
            .first()
        )

        if not token_record or not token_record.access_token:
            raise ValueError(
                f"Access token not found for user {upstox_user_id}"
            )

        return token_record.access_token

    @staticmethod
    async def get_authorized_websocket_url(
        access_token: str,
    ):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                websocket_market_data_settings.UPSTOX_MARKET_DATA_AUTHORIZE_URL,
                headers=headers,
            )

            response.raise_for_status()
            response_data = response.json()

            if response_data.get("status") != "success":
                raise ValueError(
                    "Upstox market data authorization failed"
                )

            authorized_url = (
                response_data
                .get("data", {})
                .get("authorized_redirect_uri")
            )

            if not authorized_url:
                raise ValueError(
                    "authorized_redirect_uri not found in Upstox response"
                )

            if not authorized_url.startswith("wss://"):
                raise ValueError(
                    "Invalid Upstox WebSocket URL"
                )

            return authorized_url

    @staticmethod
    def decode_market_data(raw_message: bytes):
        feed_response = MarketDataFeedV3_pb2.FeedResponse()
        feed_response.ParseFromString(raw_message)

        decoded_data = MessageToDict(feed_response)

        return decoded_data

    @staticmethod
    async def connect_market_data(
        websocket: WebSocket,
        upstox_user_id: str,
        subscription: MarketDataSubscriptionRequest,
        db: Session,
    ):
        try:
            access_token = (
                WebsocketMarketDataService.get_access_token(
                    upstox_user_id=upstox_user_id,
                    db=db,
                )
            )

            authorized_url = (
                await WebsocketMarketDataService
                .get_authorized_websocket_url(access_token)
            )

            async with websockets.connect(
                authorized_url,
                ping_interval=20,
                ping_timeout=20,
            ) as upstox_ws:

                await websocket.send_json({
                    "success": True,
                    "message": "Connected to Upstox Market Data Feed V3",
                    "upstox_user_id": upstox_user_id,
                })

                # Subscription request
                subscription_message = json.dumps(
                    subscription.model_dump()
                ).encode("utf-8")

                await upstox_ws.send(subscription_message)

                while True:
                    raw_message = await upstox_ws.recv()

                    if isinstance(raw_message, bytes):
                        decoded_data = (
                            WebsocketMarketDataService
                            .decode_market_data(raw_message)
                        )

                        await websocket.send_json(decoded_data)

                    elif isinstance(raw_message, str):
                        await websocket.send_text(raw_message)

        except WebSocketDisconnect:
            logger.info(
                "Frontend disconnected for user %s",
                upstox_user_id,
            )

        except websockets.ConnectionClosed:
            logger.info(
                "Upstox WebSocket closed for user %s",
                upstox_user_id,
            )

        except Exception as exc:
            logger.exception(
                "Market data connection failed for user %s",
                upstox_user_id,
            )

            try:
                await websocket.send_json({
                    "success": False,
                    "message": "Market data connection failed",
                    "detail": str(exc),
                })
            except Exception:
                pass
            
            
            
            

#     @staticmethod
#     async def connect_portfolio_stream(
#         websocket: WebSocket,
#         upstox_user_id: str,
#         db: Session,
#         update_types: str = "order",
#     ):
#         """
#         Connect to Upstox Portfolio Stream using PortfolioDataStreamer SDK.
#         """
#
#         streamer = None
#         connect_task = None
#
#         try:
#             # Get access token from database
#             access_token = (
#                 WebsocketMarketDataService.get_access_token(
#                     upstox_user_id=upstox_user_id,
#                     db=db,
#                 )
#             )
#
#             # Validate update types
#             supported_types = {
#                 "order",
#                 "gtt_order",
#                 "position",
#                 "holding",
#             }
#
#             requested_types = {
#                 item.strip().lower()
#                 for item in update_types.split(",")
#                 if item.strip()
#             }
#
#             if not requested_types:
#                 requested_types = {"order"}
#
#             invalid_types = requested_types - supported_types
#
#             if invalid_types:
#                 raise ValueError(
#                     f"Invalid update types: {', '.join(sorted(invalid_types))}"
#                 )
#
#             # Configure Upstox SDK
#             configuration = upstox_client.Configuration()
#             configuration.access_token = access_token
#
#             api_client = upstox_client.ApiClient(configuration)
#
#             # Initialize Portfolio Data Streamer
#             streamer = upstox_client.PortfolioDataStreamer(
#                 api_client,
#                 order_update="order" in requested_types,
#                 position_update="position" in requested_types,
#                 holding_update="holding" in requested_types,
#                 gtt_update="gtt_order" in requested_types,
#             )
#
#             # Create async message queue
#             loop = asyncio.get_running_loop()
#             message_queue = asyncio.Queue()
#
#             def send_to_queue(event_type, data=None):
#                 try:
#                     loop.call_soon_threadsafe(
#                         message_queue.put_nowait,
#                         (event_type, data),
#                     )
#                 except RuntimeError:
#                     logger.warning(
#                         "Portfolio Stream event loop is closed for user %s",
#                         upstox_user_id,
#                     )
#
#             # SDK open event
#             def on_open(*args):
#                 logger.info(
#                     "Portfolio Stream connected for user %s",
#                     upstox_user_id,
#                 )
#                 send_to_queue("open")
#
#             # SDK message event
#             def on_message(message):
#                 send_to_queue("message", message)
#
#             # SDK error event
#             def on_error(error):
#                 logger.error(
#                     "Portfolio Stream error for user %s: %s",
#                     upstox_user_id,
#                     error,
#                 )
#                 send_to_queue("error", str(error))
#
#             # SDK close event
#             def on_close(*args):
#                 logger.info(
#                     "Portfolio Stream closed for user %s",
#                     upstox_user_id,
#                 )
#                 send_to_queue("close")
#
#             # Register SDK events
#             streamer.on("open", on_open)
#             streamer.on("message", on_message)
#             streamer.on("error", on_error)
#             streamer.on("close", on_close)
#
#             # Enable automatic reconnection
#             streamer.auto_reconnect(True, 10, 5)
#
#             # Run blocking SDK connection in background thread
#             connect_task = asyncio.create_task(
#                 asyncio.to_thread(streamer.connect)
#             )
#
#             def connection_finished(task):
#                 try:
#                     exception = task.exception()
#
#                     if exception:
#                         send_to_queue("error", str(exception))
#
#                 except asyncio.CancelledError:
#                     pass
#
#                 send_to_queue("connect_done")
#
#             connect_task.add_done_callback(connection_finished)
#
#             await websocket.send_json({
#                 "success": True,
#                 "message": "Portfolio Stream connection starting",
#                 "upstox_user_id": upstox_user_id,
#                 "update_types": sorted(requested_types),
#             })
#
#             # Forward SDK events to frontend
#             while True:
#                 event_type, data = await message_queue.get()
#
#                 if event_type == "message":
#                     if isinstance(data, dict):
#                         await websocket.send_json(data)
#
#                     elif isinstance(data, bytes):
#                         await websocket.send_bytes(data)
#
#                     elif isinstance(data, str):
#                         try:
#                             parsed_data = json.loads(data)
#                             await websocket.send_json(parsed_data)
#                         except json.JSONDecodeError:
#                             await websocket.send_text(data)
#
#                     else:
#                         await websocket.send_json({
#                             "data": str(data),
#                         })
#
#                 elif event_type == "open":
#                     await websocket.send_json({
#                         "success": True,
#                         "message": "Portfolio Stream connected successfully",
#                     })
#
#                 elif event_type == "error":
#                     await websocket.send_json({
#                         "success": False,
#                         "message": "Portfolio Stream error",
#                         "detail": data,
#                     })
#
#                 elif event_type == "close":
#                     await websocket.send_json({
#                         "success": False,
#                         "message": "Portfolio Stream connection closed",
#                     })
#
#                 elif event_type == "connect_done":
#                     break
#
#         except WebSocketDisconnect:
#             logger.info(
#                 "Frontend disconnected from Portfolio Stream for user %s",
#                 upstox_user_id,
#             )
#
#         except Exception as exc:
#             logger.exception(
#                 "Portfolio Stream connection failed for user %s",
#                 upstox_user_id,
#             )
#
#             try:
#                 await websocket.send_json({
#                     "success": False,
#                     "message": "Portfolio Stream connection failed",
#                     "detail": str(exc),
#                 })
#             except Exception:
#                 pass
#
#         finally:
#             # Disconnect SDK streamer
#             if streamer is not None:
#                 try:
#                     await asyncio.to_thread(streamer.disconnect)
#                 except Exception:
#                     logger.exception(
#                         "Portfolio Stream disconnect failed for user %s",
#                         upstox_user_id,
#                     )
#
#             if connect_task is not None and not connect_task.done():
#                 connect_task.cancel()
#                
#
#     @staticmethod
#     async def get_authorized_portfolio_websocket_url(
#         access_token: str,
#         update_types: str = "order",
#     ) -> str:
#
#         requested_types = [
#             item.strip().lower()
#             for item in update_types.split(",")
#             if item.strip()
#         ]
#
#         if not requested_types:
#             requested_types = ["order"]
#
#         portfolio_request = PortfolioStreamRequest(
#             update_types=requested_types
#         )
#
#         headers = {
#             "Authorization": f"Bearer {access_token}",
#             "Accept": "application/json",
#         }
#
#         async with httpx.AsyncClient(timeout=20.0) as client:
#             response = await client.get(
#                 websocket_market_data_settings.UPSTOX_PORTFOLIO_STREAM_AUTHORIZE_URL,
#                 headers=headers,
#                 params={
#                     "update_types": ",".join(
#                         portfolio_request.update_types
#                     )
#                 },
#             )
#
#             response.raise_for_status()
#             response_data = response.json()
#
#             if response_data.get("status") != "success":
#                 raise ValueError(
#                     "Upstox Portfolio Stream authorization failed"
#                 )
#
#             authorized_url = (
#                 response_data
#                 .get("data", {})
#                 .get("authorized_redirect_uri")
#             )
#
#             if not authorized_url:
#                 raise ValueError(
#                     "authorized_redirect_uri not found in response"
#                 )
#
#             if not authorized_url.startswith("wss://"):
#                 raise ValueError(
#                     "Invalid Upstox Portfolio WebSocket URL"
#                 )
#
#             return authorized_url
