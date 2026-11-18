
# import asyncio
# import json
# import logging
# import uuid

# import websockets
# from fastapi import WebSocket, WebSocketDisconnect
# from sqlalchemy.orm import Session

# from config.index_data_config import (
#     DEFAULT_INDICES,
#     MARKET_DATA_MODE,
# )
# from services.websocket_market_data_service import (
#     WebsocketMarketDataService,
# )


# logger = logging.getLogger(__name__)


# class IndexDataService:

#     @staticmethod
#     async def stream_indices(
#         websocket: WebSocket,
#         upstox_user_id: str,
#         db: Session,
#     ):
#         await websocket.accept()

#         retry_delay = 2
#         first_connection = True

#         try:
#             # Step 1: Get saved Upstox access token
#             access_token = (
#                 WebsocketMarketDataService.get_access_token(
#                     upstox_user_id,
#                     db,
#                 )
#             )

#             if not access_token:
#                 await websocket.send_json({
#                     "type": "error",
#                     "message": "Upstox access token not found. Please login first.",
#                 })
#                 return

#             # Step 2: Connect and automatically reconnect
#             while True:

#                 try:
#                     # Get a fresh authorized URL for every connection
#                     ws_url = await (
#                         WebsocketMarketDataService
#                         .get_authorized_websocket_url(access_token)
#                     )

#                     if not ws_url:
#                         raise Exception(
#                             "Upstox authorized WebSocket URL not received."
#                         )

#                     # Step 3: Connect to Upstox WebSocket
#                     async with websockets.connect(
#                         ws_url,
#                         ping_interval=None,
#                         close_timeout=10,
#                         max_size=None,
#                     ) as upstox_ws:

#                         logger.info(
#                             "Upstox WebSocket connected for user %s",
#                             upstox_user_id,
#                         )

#                         if first_connection:
#                             await websocket.send_json({
#                                 "type": "connection",
#                                 "status": "connected",
#                                 "message": "Upstox WebSocket connected successfully.",
#                             })
#                         else:
#                             await websocket.send_json({
#                                 "type": "connection",
#                                 "status": "connected",
#                                 "message": "Upstox WebSocket reconnected successfully.",
#                             })

#                         # Step 4: Automatically subscribe all six indices
#                         subscription_message = {
#                             "guid": str(uuid.uuid4()),
#                             "method": "sub",
#                             "data": {
#                                 "mode": MARKET_DATA_MODE,
#                                 "instrumentKeys": list(
#                                     DEFAULT_INDICES.values()
#                                 ),
#                             },
#                         }

#                         await upstox_ws.send(
#                             json.dumps(subscription_message).encode("utf-8")
#                         )

#                         logger.info(
#                             "Index subscription request sent for user %s: %s",
#                             upstox_user_id,
#                             list(DEFAULT_INDICES.keys()),
#                         )

#                         await websocket.send_json({
#                             "type": "subscription",
#                             "status": "request_sent",
#                             "indices": list(DEFAULT_INDICES.keys()),
#                             "message": (
#                                 "Subscription request sent for all six indices. "
#                                 "Waiting for live data."
#                             ),
#                         })

#                         first_connection = False
#                         retry_delay = 2

#                         # Step 5: Continuously receive and forward live data
#                         while True:

#                             raw_message = await upstox_ws.recv()

#                             if not isinstance(raw_message, bytes):
#                                 logger.warning(
#                                     "Received non-binary message from Upstox."
#                                 )
#                                 continue

#                             # Decode using existing service
#                             market_data = (
#                                 WebsocketMarketDataService.decode_market_data(
#                                     raw_message
#                                 )
#                             )

#                             # Forward decoded JSON data to browser
#                             await websocket.send_json(market_data)

#                 except WebSocketDisconnect:
#                     logger.info(
#                         "Browser disconnected from index feed: %s",
#                         upstox_user_id,
#                     )
#                     break

#                 except websockets.ConnectionClosed as exc:
#                     logger.warning(
#                         "Upstox WebSocket closed for %s: %s",
#                         upstox_user_id,
#                         exc,
#                     )

#                 except (OSError, asyncio.TimeoutError) as exc:
#                     logger.warning(
#                         "Upstox connection error for %s: %s",
#                         upstox_user_id,
#                         exc,
#                     )

#                 # Step 6: Reconnect after temporary connection failure
#                 await websocket.send_json({
#                     "type": "connection",
#                     "status": "reconnecting",
#                     "message": (
#                         f"Upstox connection lost. Retrying in "
#                         f"{retry_delay} seconds..."
#                     ),
#                 })

#                 await asyncio.sleep(retry_delay)

#                 retry_delay = min(retry_delay * 2, 30)

#         except WebSocketDisconnect:
#             logger.info(
#                 "Browser disconnected from index feed: %s",
#                 upstox_user_id,
#             )

#         except Exception as exc:
#             logger.exception(
#                 "Index WebSocket error for %s",
#                 upstox_user_id,
#             )

#             try:
#                 await websocket.send_json({
#                     "type": "error",
#                     "message": str(exc),
#                 })
#             except Exception:
#                 pass




import asyncio
import json
import logging
import uuid

import httpx
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from config.index_data_config import (
    DEFAULT_INDICES,
    MARKET_DATA_MODE,
)

from services.websocket_market_data_service import (
    WebsocketMarketDataService,
)


logger = logging.getLogger("uvicorn.error")

MARKET_STATUS_URL = "https://api.upstox.com/v2/market/status/{}"
MARKET_STATUS_POLL_SECONDS = 5


class IndexDataService:

    @staticmethod
    async def monitor_exchange_status(
        access_token: str,
        segment_status: dict,
        stop_event: asyncio.Event,
    ):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            while not stop_event.is_set():
                async def fetch_status(exchange: str, segment: str):
                    try:
                        response = await client.get(
                            MARKET_STATUS_URL.format(exchange),
                            headers=headers,
                        )
                        response.raise_for_status()
                        response_data = response.json()
                        status = (
                            response_data.get("data", {}).get("status")
                            if response_data.get("status") == "success"
                            else None
                        )

                        if status:
                            segment_status[segment] = status

                    except (httpx.HTTPError, ValueError) as exc:
                        logger.warning(
                            "Could not refresh %s market status: %s",
                            exchange,
                            exc,
                        )

                await asyncio.gather(
                    fetch_status("NSE", "NSE_INDEX"),
                    fetch_status("BSE", "BSE_INDEX"),
                )

                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=MARKET_STATUS_POLL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    pass

    @staticmethod
    async def wait_for_browser_disconnect(websocket: WebSocket):
        try:
            while True:
                message = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    return

        except WebSocketDisconnect:
            return

    @staticmethod
    async def stream_indices(
        websocket: WebSocket,
        upstox_user_id: str,
        db: Session,
    ):
        await websocket.accept()

        retry_delay = 2
        max_retry_delay = 30
        first_connection = True
        browser_disconnected = False
        market_status_by_segment = {}
        initial_snapshot_seen = set()
        market_status_stop = asyncio.Event()
        market_status_task = None
        disconnect_task = asyncio.create_task(
            IndexDataService.wait_for_browser_disconnect(websocket)
        )

        try:
            if upstox_user_id == "current":
                upstox_user_id = (
                    WebsocketMarketDataService
                    .get_latest_access_token_user_id(db)
                )

            # Step 1: Get saved Upstox access token
            access_token = (
                WebsocketMarketDataService.get_access_token(
                    upstox_user_id,
                    db,
                )
            )

            if not access_token:
                await websocket.send_json({
                    "type": "error",
                    "message": "Upstox access token not found. Please login first.",
                })
                await websocket.close()
                return

            market_status_task = asyncio.create_task(
                IndexDataService.monitor_exchange_status(
                    access_token,
                    market_status_by_segment,
                    market_status_stop,
                )
            )

            # Step 2: Automatically reconnect when Upstox disconnects
            while not browser_disconnected:

                try:
                    # Get fresh authorized WebSocket URL
                    ws_url = await (
                        WebsocketMarketDataService
                        .get_authorized_websocket_url(access_token)
                    )

                    if not ws_url:
                        raise ConnectionError(
                            "Upstox authorized WebSocket URL not received."
                        )

                    # Step 3: Connect to Upstox WebSocket
                    async with websockets.connect(
                        ws_url,
                        # Upstox sends heartbeat pings; the WebSocket client
                        # replies with pong automatically. Avoid client pings
                        # that can time out against the Upstox feed endpoint.
                        ping_interval=None,
                        ping_timeout=None,
                        close_timeout=10,
                        open_timeout=20,
                        max_size=None,
                    ) as upstox_ws:

                        logger.info(
                            "Upstox WebSocket connection OPEN for user %s",
                            upstox_user_id,
                        )

                        message = (
                            "Upstox WebSocket connected successfully."
                            if first_connection
                            else "Upstox WebSocket reconnected successfully."
                        )

                        await websocket.send_json({
                            "type": "connection",
                            "status": "connected",
                            "message": message,
                        })

                        # Step 4: Subscribe all six indices
                        subscription_message = {
                            "guid": str(uuid.uuid4()),
                            "method": "sub",
                            "data": {
                                "mode": MARKET_DATA_MODE,
                                "instrumentKeys": list(
                                    DEFAULT_INDICES.values()
                                ),
                            },
                        }

                        await upstox_ws.send(
                            json.dumps(subscription_message).encode("utf-8")
                        )

                        logger.info(
                            "Index subscription request sent for user %s: %s",
                            upstox_user_id,
                            list(DEFAULT_INDICES.keys()),
                        )

                        await websocket.send_json({
                            "type": "subscription",
                            "status": "request_sent",
                            "indices": list(DEFAULT_INDICES.keys()),
                            "message": (
                                "Subscription request sent for all six indices. "
                                "Waiting for live data."
                            ),
                        })

                        first_connection = False
                        retry_delay = 2

                        # Step 5: Receive and forward continuous live data
                        upstox_receive_task = asyncio.create_task(
                            upstox_ws.recv()
                        )

                        try:
                            while True:
                                done, _ = await asyncio.wait(
                                    {
                                        upstox_receive_task,
                                        disconnect_task,
                                    },
                                    return_when=asyncio.FIRST_COMPLETED,
                                )

                                if disconnect_task in done:
                                    browser_disconnected = True
                                    break

                                raw_message = upstox_receive_task.result()
                                upstox_receive_task = asyncio.create_task(
                                    upstox_ws.recv()
                                )

                                if isinstance(raw_message, bytes):

                                    market_data = (
                                        WebsocketMarketDataService
                                        .decode_market_data(raw_message)
                                    )

                                    market_info = market_data.get("marketInfo", {})
                                    feed_status = market_info.get("segmentStatus", {})
                                    market_status_by_segment.update(feed_status)

                                    # Upstox sends this status message once per
                                    # connection. It has no index prices to show.
                                    if market_data.get("type") == "market_info":
                                        continue

                                    feeds = market_data.get("feeds")
                                    if isinstance(feeds, dict):
                                        visible_feeds = {}

                                        for instrument_key, instrument_feed in feeds.items():
                                            segment = instrument_key.split("|", 1)[0]
                                            status = market_status_by_segment.get(segment)

                                            # A closed market still sends one
                                            # initial snapshot. Keep that closing
                                            # value, then ignore further ticks
                                            # until the exchange opens again.
                                            if (
                                                status == "NORMAL_OPEN"
                                                or instrument_key not in initial_snapshot_seen
                                            ):
                                                visible_feeds[instrument_key] = instrument_feed
                                                initial_snapshot_seen.add(instrument_key)

                                        if not visible_feeds:
                                            continue

                                        market_data["feeds"] = visible_feeds

                                    await websocket.send_json(market_data)

                                elif isinstance(raw_message, str):

                                    try:
                                        await websocket.send_json(
                                            json.loads(raw_message)
                                        )
                                    except json.JSONDecodeError:
                                        await websocket.send_text(raw_message)

                        finally:
                            if not upstox_receive_task.done():
                                upstox_receive_task.cancel()

                            await asyncio.gather(
                                upstox_receive_task,
                                return_exceptions=True,
                            )

                except WebSocketDisconnect:
                    browser_disconnected = True

                    logger.info(
                        "Browser disconnected for user %s",
                        upstox_user_id,
                    )

                    break

                except websockets.ConnectionClosed as exc:

                    logger.warning(
                        "Upstox WebSocket disconnected for %s: %s",
                        upstox_user_id,
                        exc,
                    )

                except (OSError, asyncio.TimeoutError, ConnectionError) as exc:

                    logger.warning(
                        "Upstox connection error for %s: %s",
                        upstox_user_id,
                        exc,
                    )

                except Exception as exc:

                    logger.exception(
                        "Index feed error for user %s",
                        upstox_user_id,
                    )

                    # Do not retry permanent application errors forever
                    if isinstance(exc, ValueError):
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "message": str(exc),
                            })
                        except Exception:
                            pass
                        break

                # Step 6: Check whether browser is still connected
                if browser_disconnected:
                    break

                try:
                    await websocket.send_json({
                        "type": "connection",
                        "status": "reconnecting",
                        "message": (
                            f"Upstox connection lost. Retrying in "
                            f"{retry_delay} seconds..."
                        ),
                    })

                except Exception:
                    logger.info(
                        "Browser connection lost for user %s",
                        upstox_user_id,
                    )
                    browser_disconnected = True
                    break

                try:
                    await asyncio.wait_for(
                        asyncio.shield(disconnect_task),
                        timeout=retry_delay,
                    )
                    browser_disconnected = True
                    break
                except asyncio.TimeoutError:
                    pass

                retry_delay = min(
                    retry_delay * 2,
                    max_retry_delay,
                )

        except WebSocketDisconnect:

            logger.info(
                "Browser disconnected from index feed: %s",
                upstox_user_id,
            )

        except Exception as exc:

            logger.exception(
                "Index WebSocket error for user %s",
                upstox_user_id,
            )

            try:
                await websocket.send_json({
                    "type": "error",
                    "message": "Market data connection failed.",
                    "detail": str(exc),
                })
            except Exception:
                pass

        finally:

            market_status_stop.set()

            if market_status_task is not None and not market_status_task.done():
                market_status_task.cancel()
                await asyncio.gather(
                    market_status_task,
                    return_exceptions=True,
                )

            if not disconnect_task.done():
                disconnect_task.cancel()
                await asyncio.gather(
                    disconnect_task,
                    return_exceptions=True,
                )

            logger.info(
                "Index feed stopped for user %s",
                upstox_user_id,
            )
