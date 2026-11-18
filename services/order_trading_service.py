import json
import logging,os
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from config.order_trading_config import order_trading_settings
from models.upstox_user_login import AccessToken
from models.order_trading import OrderTrading
from models.multi_order_trading import MultiOrderTrading
from schemas.order_trading_schemas import (
    PlaceOrderRequest,
    MultiOrderRequest,
    ModifyOrderRequest,
)

logger = logging.getLogger(__name__)


class OrderTradingService:

    @staticmethod
    def _has_upstox_error_code(response_data: object, error_code: str) -> bool:
        """Search nested Upstox single or multi-order error responses."""
        pending = [response_data]

        while pending:
            value = pending.pop()

            if isinstance(value, dict):
                if (
                    value.get("errorCode") == error_code
                    or value.get("error_code") == error_code
                ):
                    return True

                pending.extend(value.values())

            elif isinstance(value, list):
                pending.extend(value)

        return False

    @staticmethod
    def _amo_not_supported_detail(response_data: object) -> dict:
        return {
            "message": (
                "Upstox classified this request as an After Market Order "
                "(UDAPI1162), which cannot be placed through this API. "
                "No order was placed. Retry during the instrument's active "
                "market session, or place the AMO through Upstox web/mobile. "
                "Upstox determines this from the market session; "
                "is_amo=false does not force a live order."
            ),
            "error_code": "UDAPI1162",
            "upstox_response": response_data,
        }

    @staticmethod
    def get_access_token(upstox_user_id: str, db: Session) -> str:

        token_record = (
            db.query(AccessToken)
            .filter(AccessToken.upstox_user_id == upstox_user_id)
            .order_by(AccessToken.id.desc())
            .first()
        )

        if not token_record or not token_record.access_token:
            raise HTTPException(
                status_code=401,
                detail="A valid Upstox access token was not found for this user.",
            )
        return token_record.access_token


# Place _single_order 

    @staticmethod
    async def place_order(
        upstox_user_id: str,
        order: PlaceOrderRequest,
        db: Session,
    ) -> dict:

        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        url = order_trading_settings.UPSTOX_PLACE_ORDER_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = order.model_dump(exclude_none=True)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )

        except httpx.TimeoutException:
            logger.exception(
                "Order placement request timed out for upstox_user_id=%s",
                upstox_user_id,
            )

            raise HTTPException(
                status_code=504,
                detail=(
                    "The order request timed out. Check the order status "
                    "before attempting another order."
                ),
            )

        except httpx.RequestError:
            logger.exception(
                "Unable to connect to Upstox for upstox_user_id=%s",
                upstox_user_id,
            )

            raise HTTPException(
                status_code=502,
                detail="Unable to connect to the Upstox API.",
            )

        try:
            response_data = response.json()
        except ValueError:
            response_data = {
                "detail": "Upstox returned an invalid JSON response."
            }

        if OrderTradingService._has_upstox_error_code(
            response_data,
            "UDAPI1162",
        ):
            raise HTTPException(
                status_code=400,
                detail=OrderTradingService._amo_not_supported_detail(
                    response_data
                ),
            )

        if not response.is_success:
            logger.warning(
                "Upstox order request failed for upstox_user_id=%s, status=%s",
                upstox_user_id,
                response.status_code,
            )

            raise HTTPException(
                status_code=response.status_code,
                detail=response_data,
            )

        order_ids = response_data.get("data", {}).get("order_ids", [])

        if not order_ids:
            logger.error(
                "Upstox returned success without order IDs for upstox_user_id=%s",
                upstox_user_id,
            )

            raise HTTPException(
                status_code=502,
                detail="Upstox did not return any order IDs.",
            )

        try:
            for order_id in order_ids:

                saved_order = OrderTrading(
                    upstox_user_id=upstox_user_id,
                    upstox_order_id=str(order_id),
                    instrument_token=order.instrument_token,
                    quantity=order.quantity,
                    product=order.product,
                    validity=order.validity,
                    price=order.price,
                    order_type=order.order_type,
                    transaction_type=order.transaction_type,
                    tag=order.tag,
                    disclosed_quantity=order.disclosed_quantity,
                    trigger_price=order.trigger_price,
                    is_amo=order.is_amo,
                    slice=order.slice,
                    market_protection=order.market_protection,
                    status="PLACED",
                    upstox_response=json.dumps(response_data),
                )

                db.add(saved_order)

            db.commit()

        except Exception:
            db.rollback()

            logger.exception(
                "Order was accepted by Upstox but saving its record failed "
                "for upstox_user_id=%s. Order IDs=%s",
                upstox_user_id,
                order_ids,
            )

            raise HTTPException(
                status_code=500,
                detail={
                    "message": (
                        "Upstox accepted the order request, but saving the "
                        "order record to the database failed. Check Upstox "
                        "order status before retrying."
                    ),
                    "order_ids": order_ids,
                },
            )

        return response_data
    
    
    # Place Multi_Order
    
    @staticmethod
    async def place_multi_order(
        upstox_user_id: str,
        request: MultiOrderRequest,
        db: Session,
    ) -> dict:
        """
        Place multiple orders using the Upstox Multi Order API
        and save the results immediately in the database.
        """

        # 1. Validate correlation IDs.
        correlation_ids = [
            order.correlation_id
            for order in request.orders
        ]

        if len(correlation_ids) != len(set(correlation_ids)):
            raise HTTPException(
                status_code=422,
                detail="Duplicate correlation_id found in request.",
            )

        # 2. Check existing correlation IDs.
        existing_order = (
            db.query(MultiOrderTrading.correlation_id)
            .filter(
                MultiOrderTrading.correlation_id.in_(
                    correlation_ids
                )
            )
            .first()
        )

        if existing_order:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"correlation_id {existing_order[0]} already exists. "
                    "Please use a new correlation_id."
                ),
            )

        # 3. Get the saved access token.
        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        # 4. Get URL from .env.
        url = order_trading_settings.UPSTOX_MULTI_ORDER_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 5. Prepare payload.
        payload = []

        for order in request.orders:
            order_data = order.model_dump(exclude_none=True)
            order_data["correlation_id"] = str(
                order.correlation_id
            )
            payload.append(order_data)

        # 6. Send request to Upstox.
        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )

        except httpx.TimeoutException:
            logger.exception(
                "Multi-order request timed out for upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=504,
                detail=(
                    "Request timed out. Check Upstox order status "
                    "before retrying."
                ),
            )

        except httpx.RequestError:
            logger.exception(
                "Unable to connect to Upstox for upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=502,
                detail="Unable to connect to the Upstox API.",
            )

        # 7. Parse response.
        try:
            response_data = response.json()
        except ValueError:
            logger.error(
                "Invalid Upstox response: %s",
                response.text,
            )
            raise HTTPException(
                status_code=502,
                detail="Upstox returned an invalid JSON response.",
            )

        upstream_items = (
            response_data.get("data", [])
            if isinstance(response_data, dict)
            else []
        )
        if not isinstance(upstream_items, list):
            upstream_items = []

        has_placed_order = any(
            isinstance(item, dict) and item.get("order_id")
            for item in upstream_items
        )

        if (
            not has_placed_order
            and OrderTradingService._has_upstox_error_code(
                response_data,
                "UDAPI1162",
            )
        ):
            raise HTTPException(
                status_code=400,
                detail=OrderTradingService._amo_not_supported_detail(
                    response_data
                ),
            )

        # 8. Handle Upstox errors.
        if not response.is_success:
            logger.error(
                "Upstox multi-order failed. upstox_user_id=%s status=%s response=%s",
                upstox_user_id,
                response.status_code,
                response.text,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Upstox multi-order request failed.",
                    "upstox_status_code": response.status_code,
                    "upstox_response": response_data,
                },
            )

        if not isinstance(response_data, dict):
            raise HTTPException(
                status_code=502,
                detail="Unexpected response format from Upstox.",
            )

        response_items = response_data.get("data", [])

        if not isinstance(response_items, list):
            response_items = []

        has_placed_order = any(
            isinstance(item, dict) and item.get("order_id")
            for item in response_items
        )

        if response_data.get("status") == "error" and not has_placed_order:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Upstox rejected all orders in this request. "
                        "No orders were placed."
                    ),
                    "upstox_response": response_data,
                },
            )

        # 9. Match response to original orders.
        orders_by_correlation_id = {
            str(order.correlation_id): order
            for order in request.orders
        }

        saved_count = 0

        # 10. Save results and commit immediately.
        try:
            for item in response_items:
                if not isinstance(item, dict):
                    continue

                response_correlation_id = item.get(
                    "correlation_id"
                )

                if response_correlation_id is None:
                    continue

                original_order = orders_by_correlation_id.get(
                    str(response_correlation_id)
                )

                if original_order is None:
                    logger.warning(
                        "Unknown correlation_id from Upstox: %s",
                        response_correlation_id,
                    )
                    continue

                order_id = item.get("order_id")

                db_record = MultiOrderTrading(
                    upstox_user_id=upstox_user_id,
                    correlation_id=int(
                        original_order.correlation_id
                    ),
                    upstox_order_id=(
                        str(order_id) if order_id else None
                    ),
                    instrument_token=original_order.instrument_token,
                    quantity=original_order.quantity,
                    product=original_order.product,
                    validity=original_order.validity,
                    price=original_order.price,
                    order_type=original_order.order_type,
                    transaction_type=original_order.transaction_type,
                    tag=original_order.tag,
                    disclosed_quantity=original_order.disclosed_quantity,
                    trigger_price=original_order.trigger_price,
                    is_amo=original_order.is_amo,
                    slice=original_order.slice,
                    market_protection=original_order.market_protection,
                    status=(
                        "PLACED" if order_id else "ERROR"
                    ),
                    upstox_response=json.dumps(item),
                )

                db.add(db_record)
                saved_count += 1

            # Persist records before returning the response.
            db.flush()
            db.commit()

            # Refresh saved records from the database.
            db.expire_all()

            logger.info(
                "Multi-orders saved successfully. upstox_user_id=%s saved_count=%s",
                upstox_user_id,
                saved_count,
            )

        except Exception:
            db.rollback()

            logger.exception(
                "Failed to save multi-order results for upstox_user_id=%s",
                upstox_user_id,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Upstox responded, but saving orders to the "
                    "database failed. Check order status before retrying."
                ),
            )

        # 11. Return only after database commit.
        response_data["database_saved_count"] = saved_count

        return response_data
    
    
    # MODIFY ORDER 
    
    @staticmethod
    async def modify_order(
        upstox_user_id: str,
        request: ModifyOrderRequest,
        db: Session,
    ) -> dict:
        """
        Modify an Upstox order.

        Search in order_trading first, then multi_order_trading.
        Update the local database for testing even if Upstox fails.
        Return Upstox response and database update details.
        """

        # 1. Find the order in the single-order table first.
        db_order = (
            db.query(OrderTrading)
            .filter(
                OrderTrading.upstox_user_id == upstox_user_id,
                OrderTrading.upstox_order_id == request.order_id,
            )
            .first()
        )

        table_name = "order_trading"

        # 2. If not found, search in the multi-order table.
        if db_order is None:
            db_order = (
                db.query(MultiOrderTrading)
                .filter(
                    MultiOrderTrading.upstox_user_id == upstox_user_id,
                    MultiOrderTrading.upstox_order_id == request.order_id,
                )
                .first()
            )

            table_name = "multi_order_trading"

        # 3. If order is not found in either table.
        if db_order is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": (
                        "Order not found in order_trading "
                        "or multi_order_trading table."
                    ),
                    "database_updated": False,
                },
            )

        # 4. Prepare modified values.
        modified_values = request.model_dump(
            exclude={"order_id"},
            exclude_none=True,
        )

        # 5. Get the user's saved access token.
        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        # 6. Read URL from .env.
        url = order_trading_settings.UPSTOX_MODIFY_ORDER_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 7. Send modification request to Upstox.
        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:
                response = await client.put(
                    url,
                    headers=headers,
                    json=request.model_dump(exclude_none=True),
                )

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail={
                    "message": "Upstox request timed out.",
                    "database_updated": False,
                    "warning": (
                        "Upstox may have processed the request. "
                        "Check order status before retrying."
                    ),
                },
            )

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Unable to connect to Upstox.",
                    "error": str(exc),
                    "database_updated": False,
                },
            )

        # 8. Parse the Upstox response.
        try:
            upstox_response = response.json()
        except ValueError:
            upstox_response = {
                "message": response.text
            }

        # 9. Update the local database.
        try:
            for field, value in modified_values.items():
                if hasattr(type(db_order), field):
                    setattr(db_order, field, value)

            # Preserve the same status and response format.
            if response.is_success:
                db_order.status = "MODIFIED"
            else:
                # Testing only: Upstox failed, but update local DB.
                db_order.status = "LOCAL_MODIFIED"

            db.commit()
            db.refresh(db_order)

        except Exception:
            db.rollback()

            logger.exception(
                "Failed to update local order for upstox_user_id=%s, order_id=%s",
                upstox_user_id,
                request.order_id,
            )

            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to update local database.",
                    "database_updated": False,
                    "upstox_status_code": response.status_code,
                    "upstox_response": upstox_response,
                },
            )

        # 10. Prepare updated database details.
        updated_order = {
            "order_id": db_order.upstox_order_id,
            "quantity": getattr(db_order, "quantity", None),
            "price": getattr(db_order, "price", None),
            "validity": getattr(db_order, "validity", None),
            "order_type": getattr(db_order, "order_type", None),
            "trigger_price": getattr(db_order, "trigger_price", None),
            "disclosed_quantity": getattr(
                db_order, "disclosed_quantity", None
            ),
            "market_protection": getattr(
                db_order, "market_protection", None
            ),
            "status": db_order.status,
        }

        # Include correlation_id when the model has this field.
        if hasattr(type(db_order), "correlation_id"):
            updated_order["correlation_id"] = db_order.correlation_id

        # 11. Return the same response structure.
        if response.is_success:
            return {
                "message": "Order modified successfully on Upstox.",
                "database_updated": True,
                "database_message": (
                    "Database record updated successfully."
                ),
                "table": table_name,
                "status": "MODIFIED",
                "updated_order": updated_order,
                "upstox_status_code": response.status_code,
                "upstox_response": upstox_response,
            }

        return {
            "message": (
                "Upstox modification failed. "
                "Local database updated for testing only."
            ),
            "database_updated": True,
            "database_message": (
                "Database record updated successfully for testing."
            ),
            "table": table_name,
            "status": "LOCAL_MODIFIED",
            "updated_order": updated_order,
            "upstox_status_code": response.status_code,
            "upstox_error": upstox_response,
            "warning": (
                "Upstox order was not confirmed as modified. "
                "Only local database values were updated."
            ),
        }
           
            
# CANCEL ORDER   

    @staticmethod
    async def cancel_order(
        upstox_user_id: str,
        order_id: str,
        db: Session,
    ) -> dict:
        """
        Cancel an Upstox order.

        Search in order_trading first, then multi_order_trading.
        Update the local database for testing even if Upstox fails.
        Return Upstox response and database update details.
        """

        # 1. Search in the single-order table first.
        db_order = (
            db.query(OrderTrading)
            .filter(
                OrderTrading.upstox_user_id == upstox_user_id,
                OrderTrading.upstox_order_id == order_id,
            )
            .first()
        )

        table_name = "order_trading"

        # 2. If not found, search in the multi-order table.
        if db_order is None:
            db_order = (
                db.query(MultiOrderTrading)
                .filter(
                    MultiOrderTrading.upstox_user_id == upstox_user_id,
                    MultiOrderTrading.upstox_order_id == order_id,
                )
                .first()
            )

            table_name = "multi_order_trading"

        # 3. If the order is not found in either table.
        if db_order is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": (
                        "Order not found in order_trading "
                        "or multi_order_trading table."
                    ),
                    "database_updated": False,
                },
            )

        # 4. Get the user's saved access token.
        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        # 5. Read URL from .env.
        url = order_trading_settings.UPSTOX_CANCEL_ORDER_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 6. Send cancellation request to Upstox.
        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:
                response = await client.delete(
                    url,
                    headers=headers,
                    params={
                        "order_id": order_id,
                    },
                )

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail={
                    "message": "Upstox cancellation request timed out.",
                    "database_updated": False,
                    "warning": (
                        "Upstox may have processed the request. "
                        "Check the order status before retrying."
                    ),
                },
            )

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Unable to connect to Upstox.",
                    "error": str(exc),
                    "database_updated": False,
                },
            )

        # 7. Parse the Upstox response.
        try:
            upstox_response = response.json()
        except ValueError:
            upstox_response = {
                "message": response.text,
            }

        # 8. Check whether Upstox confirmed cancellation.
        upstox_success = (
            response.is_success
            and isinstance(upstox_response, dict)
            and upstox_response.get("status") == "success"
        )

        # 9. Update the local database.
        try:
            if upstox_success:
                db_order.status = "CANCELLED"
            else:
                # Testing only: Upstox failed, but update local DB.
                db_order.status = "LOCAL_CANCELLED"

            db.commit()
            db.refresh(db_order)

        except Exception:
            db.rollback()

            logger.exception(
                "Failed to update local order for upstox_user_id=%s, order_id=%s",
                upstox_user_id,
                order_id,
            )

            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to update local database.",
                    "database_updated": False,
                    "upstox_status_code": response.status_code,
                    "upstox_response": upstox_response,
                },
            )

        # 10. Prepare updated database details.
        updated_order = {
            "order_id": db_order.upstox_order_id,
            "quantity": getattr(db_order, "quantity", None),
            "price": getattr(db_order, "price", None),
            "validity": getattr(db_order, "validity", None),
            "order_type": getattr(db_order, "order_type", None),
            "trigger_price": getattr(db_order, "trigger_price", None),
            "status": db_order.status,
        }

        # Include correlation_id if the model has this field.
        if hasattr(type(db_order), "correlation_id"):
            updated_order["correlation_id"] = db_order.correlation_id

        # 11. Return the same response structure as modify_order.
        if upstox_success:
            return {
                "message": "Order cancelled successfully on Upstox.",
                "database_updated": True,
                "database_message": (
                    "Database record updated successfully."
                ),
                "table": table_name,
                "status": "CANCELLED",
                "updated_order": updated_order,
                "upstox_status_code": response.status_code,
                "upstox_response": upstox_response,
            }

        return {
            "message": (
                "Upstox cancellation failed. "
                "Local database updated for testing only."
            ),
            "database_updated": True,
            "database_message": (
                "Database record updated successfully for testing."
            ),
            "table": table_name,
            "status": "LOCAL_CANCELLED",
            "updated_order": updated_order,
            "upstox_status_code": response.status_code,
            "upstox_error": upstox_response,
            "warning": (
                "Upstox order was not confirmed as cancelled. "
                "Only the local database status was updated."
            ),
        }   
             
               
# Cancel Multi Order 

    @staticmethod
    async def cancel_multi_order(
        upstox_user_id: str,
        db: Session,
        segment: str = None,
        tag: str = None,
    ) -> dict:
        """
        Cancel multiple open Upstox orders using Cancel Multi Order V2.

        Search matching orders in both local database tables:
        1. order_trading
        2. multi_order_trading

        Update local database for testing, even if Upstox fails.
        Return actual Upstox response and database update details.
        """

        # 1. Prepare optional query parameters.
        params = {}

        if segment:
            params["segment"] = segment

        if tag:
            params["tag"] = tag

        # 2. Find local orders for the user.
        single_query = db.query(OrderTrading).filter(
            OrderTrading.upstox_user_id == upstox_user_id
        )

        multi_query = db.query(MultiOrderTrading).filter(
            MultiOrderTrading.upstox_user_id == upstox_user_id
        )

        # Filter by segment when the column exists.
        if segment:
            if hasattr(OrderTrading, "segment"):
                single_query = single_query.filter(
                    OrderTrading.segment == segment
                )

            if hasattr(MultiOrderTrading, "segment"):
                multi_query = multi_query.filter(
                    MultiOrderTrading.segment == segment
                )

        # Filter by tag when the column exists.
        if tag:
            if hasattr(OrderTrading, "tag"):
                single_query = single_query.filter(
                    OrderTrading.tag == tag
                )

            if hasattr(MultiOrderTrading, "tag"):
                multi_query = multi_query.filter(
                    MultiOrderTrading.tag == tag
                )

        # Only orders that may still be open.
        open_statuses = [
            "OPEN",
            "PENDING",
            "TRIGGER PENDING",
            "AMO REQ RECEIVED",
            "SUBMITTED",
            "PLACED",
        ]

        single_query = single_query.filter(
            OrderTrading.status.in_(open_statuses)
        )

        multi_query = multi_query.filter(
            MultiOrderTrading.status.in_(open_statuses)
        )

        single_orders = single_query.all()
        multi_orders = multi_query.all()

        # 3. Combine the local orders.
        local_orders = [
            ("order_trading", order)
            for order in single_orders
        ] + [
            ("multi_order_trading", order)
            for order in multi_orders
        ]

        if not local_orders:
            return {
                "message": "No matching open orders found in local database.",
                "database_updated": False,
                "database_message": "No matching local orders were found.",
                "status": "NO_OPEN_ORDERS",
                "updated_orders": [],
                "upstox_response": None,
            }

        # 4. Enforce the API limit of 10 orders.
        if len(local_orders) > 10:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Cancel Multi Order supports a maximum "
                        "of 10 orders per request."
                    ),
                    "matching_local_orders": len(local_orders),
                    "database_updated": False,
                },
            )

        # 5. Get the user's saved access token.
        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        # 6. Read URL from .env.
        url = order_trading_settings.UPSTOX_CANCEL_MULTI_ORDER_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 7. Send Cancel Multi Order request to Upstox.
        try:
            async with httpx.AsyncClient(
                timeout=30.0
            ) as client:
                response = await client.delete(
                    url,
                    headers=headers,
                    params=params,
                )

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail={
                    "message": "Upstox cancellation request timed out.",
                    "database_updated": False,
                    "warning": (
                        "Upstox may have processed the request. "
                        "Check order status before retrying."
                    ),
                },
            )

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Unable to connect to Upstox.",
                    "error": str(exc),
                    "database_updated": False,
                },
            )

        # 8. Parse actual Upstox response.
        try:
            upstox_response = response.json()
        except ValueError:
            upstox_response = {
                "message": response.text
            }

        # 9. Identify successfully cancelled order IDs.
        successful_order_ids = set()

        if isinstance(upstox_response, dict):
            data = upstox_response.get("data") or {}

            if isinstance(data, dict):
                order_ids = data.get("order_ids") or []

                successful_order_ids = {
                    str(order_id)
                    for order_id in order_ids
                }

        # 10. Update local database.
        updated_orders = []

        try:
            for table_name, db_order in local_orders:
                local_order_id = str(db_order.upstox_order_id)

                if local_order_id in successful_order_ids:
                    db_order.status = "CANCELLED"
                else:
                    # Testing only: Upstox did not confirm cancellation.
                    db_order.status = "LOCAL_CANCELLED"

                updated_orders.append(
                    {
                        "table": table_name,
                        "order_id": db_order.upstox_order_id,
                        "status": db_order.status,
                    }
                )

            db.commit()

            for _, db_order in local_orders:
                db.refresh(db_order)

        except Exception:
            db.rollback()

            logger.exception(
                "Failed to update local orders for upstox_user_id=%s",
                upstox_user_id,
            )

            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to update local database.",
                    "database_updated": False,
                    "upstox_status_code": response.status_code,
                    "upstox_response": upstox_response,
                },
            )

        # 11. Determine overall Upstox result.
        upstox_status = None

        if isinstance(upstox_response, dict):
            upstox_status = upstox_response.get("status")

        upstox_success = (
            response.is_success
            and upstox_status == "success"
        )

        partial_success = (
            response.status_code == 207
            or upstox_status == "partial_success"
        )

        # 12. Return successful response.
        if upstox_success:
            return {
                "message": "Multiple orders cancelled successfully on Upstox.",
                "database_updated": True,
                "database_message": (
                    "Local database records updated successfully."
                ),
                "status": "CANCELLED",
                "updated_orders": updated_orders,
                "upstox_status_code": response.status_code,
                "upstox_response": upstox_response,
            }

        # 13. Return partial-success response.
        if partial_success:
            return {
                "message": (
                    "Upstox returned a partial cancellation result. "
                    "Local database updated for testing."
                ),
                "database_updated": True,
                "database_message": (
                    "Local database records updated for testing."
                ),
                "status": "PARTIAL_SUCCESS",
                "updated_orders": updated_orders,
                "upstox_status_code": response.status_code,
                "upstox_error": upstox_response,
                "warning": (
                    "Only order IDs returned in Upstox data.order_ids "
                    "are marked CANCELLED. Other local orders are "
                    "marked LOCAL_CANCELLED for testing only."
                ),
            }

        # 14. Return Upstox error response.
        return {
            "message": (
                "Upstox multi-order cancellation failed. "
                "Local database updated for testing only."
            ),
            "database_updated": True,
            "database_message": (
                "Local database records updated for testing."
            ),
            "status": "LOCAL_CANCELLED",
            "updated_orders": updated_orders,
            "upstox_status_code": response.status_code,
            "upstox_error": upstox_response,
            "warning": (
                "Upstox cancellation was not confirmed. "
                "Only local database statuses were updated."
            ),
        }          


# Exit_all_positions 
  
    @staticmethod
    async def exit_all_positions(
        upstox_user_id: str,
        db: Session,
        segment: str | None = None,
        tag: str | None = None,
    ) -> dict:
        """
        Exit open Upstox positions.
        On an Upstox API error, update matching local records
        in order_trading and multi_order_trading as attempted.
        """

        allowed_segments = {
            "NSE_EQ",
            "BSE_EQ",
            "NSE_FO",
            "BSE_FO",
            "MCX_FO",
            "NCD_FO",
            "BCD_FO",
            "NSE_COM",
        }

        if segment is not None and segment not in allowed_segments:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Invalid segment.",
                    "allowed_segments": sorted(allowed_segments),
                },
            )

        # 1. Get saved access token.
        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        # 2. Get URL from .env settings.
        url = order_trading_settings.UPSTOX_EXIT_ALL_POSITIONS_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        params = {}

        if segment is not None:
            params["segment"] = segment

        if tag is not None:
            params["tag"] = tag

        # 3. Call Upstox API.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    params=params,
                )

        except httpx.TimeoutException:
            logger.exception(
                "Exit positions request timed out. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=504,
                detail=(
                    "Exit positions request timed out. "
                    "Check Upstox positions and order status "
                    "before retrying."
                ),
            )

        except httpx.RequestError:
            logger.exception(
                "Unable to connect to Upstox Exit Positions API. "
                "upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=502,
                detail="Unable to connect to the Upstox API.",
            )

        # 4. Parse Upstox response.
        try:
            response_data = response.json()
        except ValueError:
            response_data = {
                "status": "error",
                "message": "Upstox returned an invalid JSON response.",
                "raw_response": response.text,
            }

        if not isinstance(response_data, dict):
            response_data = {
                "status": "error",
                "message": "Unexpected response format from Upstox.",
                "raw_response": response_data,
            }

        # 5. Update matching local records in both tables.
        # These statuses identify records that may still be active
        # in the local order-tracking tables.
        active_statuses = {
            "PLACED",
            "OPEN",
            "PENDING",
            "PARTIALLY_FILLED",
        }

        updated_count = 0
        updated_single_count = 0
        updated_multi_count = 0

        try:
            single_records = (
                db.query(OrderTrading)
                .filter(OrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            multi_records = (
                db.query(MultiOrderTrading)
                .filter(MultiOrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            for model_name, records in (
                ("single", single_records),
                ("multi", multi_records),
            ):
                for record in records:
                    record_status = str(
                        getattr(record, "status", "") or ""
                    ).upper()

                    # Do not overwrite completed or terminal records.
                    if record_status not in active_statuses:
                        continue

                    # Apply optional tag filter.
                    if tag is not None:
                        record_tag = getattr(record, "tag", None)
                        if record_tag != tag:
                            continue

                    # Apply optional segment filter using instrument_token.
                    if segment is not None:
                        instrument_token = getattr(
                            record, "instrument_token", None
                        )

                        if not instrument_token:
                            continue

                        if not instrument_token.startswith(
                            f"{segment}|"
                        ):
                            continue

                    # This records an attempt, not a confirmed exit.
                    record.status = "LOCAL_EXIT_ATTEMPTED"

                    updated_count += 1

                    if model_name == "single":
                        updated_single_count += 1
                    else:
                        updated_multi_count += 1

            db.commit()

        except Exception:
            db.rollback()
            logger.exception(
                "Failed to update local order records after exit request. "
                "upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Upstox response received, but local database "
                    "update failed."
                ),
            )

        # 6. Return Upstox response and local DB result.
        logger.info(
            "Exit positions processed. upstox_user_id=%s "
            "upstox_status=%s single_updated=%s multi_updated=%s",
            upstox_user_id,
            response_data.get("status"),
            updated_single_count,
            updated_multi_count,
        )

        return {
            "message": (
                "Upstox exit request failed; matching local records "
                "were marked as attempted."
                if not response.is_success
                else "Upstox exit response received."
            ),
            "upstox_status_code": response.status_code,
            "upstox_response": response_data,
            "database_updated": updated_count > 0,
            "database_updated_count": updated_count,
            "order_trading_updated_count": updated_single_count,
            "multi_order_trading_updated_count": updated_multi_count,
            "database_message": (
                "Matching records marked LOCAL_EXIT_ATTEMPTED. "
                "This does not confirm that positions were exited."
                if updated_count
                else (
                    "No matching local records found with an active "
                    "status and the supplied filters."
                )
            ),
        }


# get_order_details
    
    @staticmethod
    async def get_order_book(
        upstox_user_id: str,
        db: Session,
    ) -> dict:
        """
        Retrieve Upstox order book and synchronize matching
        records from order_trading and multi_order_trading.
        """

        # 1. Fetch local database records.
        try:
            single_records = (
                db.query(OrderTrading)
                .filter(OrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            multi_records = (
                db.query(MultiOrderTrading)
                .filter(MultiOrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

        except Exception:
            db.rollback()
            logger.exception(
                "Failed to fetch local orders. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve local order records.",
            )

        # 2. Serialize database records.
        def serialize_record(record):
            fields = (
                "id",
                "upstox_user_id",
                "upstox_order_id",
                "instrument_token",
                "quantity",
                "product",
                "validity",
                "price",
                "order_type",
                "transaction_type",
                "tag",
                "status",
                "upstox_response",
            )

            result = {}

            for field in fields:
                value = getattr(record, field, None)

                if field == "upstox_response" and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (ValueError, TypeError):
                        pass

                result[field] = value

            return result

        def get_database_data(single_rows, multi_rows):
            return {
                "order_trading": [
                    serialize_record(record)
                    for record in single_rows
                ],
                "multi_order_trading": [
                    serialize_record(record)
                    for record in multi_rows
                ],
            }

        local_data = get_database_data(
            single_records,
            multi_records,
        )

        # 3. Get saved access token for this user.
        try:
            access_token = OrderTradingService.get_access_token(
                upstox_user_id=upstox_user_id,
                db=db,
            )

        except HTTPException as exc:
            return {
                "message": "Unable to retrieve Upstox access token.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "error": exc.detail,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        except Exception:
            logger.exception(
                "Access token retrieval failed. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to retrieve Upstox access token.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        if not access_token:
            return {
                "message": "Access token not found for this user.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 4. Get order book URL from existing settings.
        url = order_trading_settings.UPSTOX_ORDER_BOOK_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        # 5. Call Upstox Order Book API.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                )

        except httpx.TimeoutException:
            logger.exception(
                "Order book request timed out. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Upstox order book request timed out.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        except httpx.RequestError as exc:
            logger.exception(
                "Upstox connection failed. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to connect to Upstox.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "error": str(exc),
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 6. Parse API response.
        try:
            response_data = response.json()
        except ValueError:
            response_data = {
                "message": "Upstox returned an invalid JSON response.",
                "raw_response": response.text,
            }

        # 7. Handle Upstox HTTP errors.
        if not response.is_success:
            return {
                "message": "Upstox order book request failed.",
                "upstox_user_id": upstox_user_id,
                "upstox_status_code": response.status_code,
                "upstox_success": False,
                "upstox_response": response_data,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 8. Extract orders from API response.
        if isinstance(response_data, dict):
            orders = response_data.get("data")
        elif isinstance(response_data, list):
            orders = response_data
        else:
            orders = None

        if not isinstance(orders, list):
            return {
                "message": "Unexpected response format from Upstox.",
                "upstox_user_id": upstox_user_id,
                "upstox_status_code": response.status_code,
                "upstox_success": False,
                "upstox_response": response_data,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 9. Index local records by Upstox order ID.
        single_by_id = {}
        multi_by_id = {}

        for record in single_records:
            order_id = getattr(record, "upstox_order_id", None)

            if order_id:
                single_by_id.setdefault(
                    str(order_id), []
                ).append(record)

        for record in multi_records:
            order_id = getattr(record, "upstox_order_id", None)

            if order_id:
                multi_by_id.setdefault(
                    str(order_id), []
                ).append(record)

        updated_single = 0
        updated_multi = 0

        # 10. Update matching records only.
        try:
            for order in orders:
                if not isinstance(order, dict):
                    continue

                order_id = order.get("order_id")

                if not order_id:
                    continue

                order_id = str(order_id)
                order_status = order.get("status")
                new_response = json.dumps(order, default=str)

                # Update OrderTrading records.
                for record in single_by_id.get(order_id, []):
                    changed = False

                    if order_status:
                        new_status = str(order_status).upper()

                        if record.status != new_status:
                            record.status = new_status
                            changed = True

                    if record.upstox_response != new_response:
                        record.upstox_response = new_response
                        changed = True

                    if changed:
                        updated_single += 1

                # Update MultiOrderTrading records.
                for record in multi_by_id.get(order_id, []):
                    changed = False

                    if order_status:
                        new_status = str(order_status).upper()

                        if record.status != new_status:
                            record.status = new_status
                            changed = True

                    if record.upstox_response != new_response:
                        record.upstox_response = new_response
                        changed = True

                    if changed:
                        updated_multi += 1

            db.commit()

        except Exception:
            db.rollback()
            logger.exception(
                "Order book synchronization failed. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Upstox response was received, but database "
                    "synchronization failed."
                ),
            )

        # 11. Fetch latest database records.
        try:
            single_records = (
                db.query(OrderTrading)
                .filter(OrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            multi_records = (
                db.query(MultiOrderTrading)
                .filter(MultiOrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            local_data = get_database_data(
                single_records,
                multi_records,
            )

        except Exception:
            db.rollback()
            logger.exception(
                "Failed to fetch updated orders. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve updated order records.",
            )

        # 12. Return Upstox and database data.
        updated_count = updated_single + updated_multi

        return {
            "message": "Order book retrieved successfully.",
            "upstox_user_id": upstox_user_id,
            "upstox_status_code": response.status_code,
            "upstox_success": True,
            "upstox_order_count": len(orders),
            "upstox_response": orders,
            "database_data": local_data,
            "database_updated": updated_count > 0,
            "database_updated_count": updated_count,
            "order_trading_updated_count": updated_single,
            "multi_order_trading_updated_count": updated_multi,
        }

    
        
        
        
        
        
        #  get_order_history 
        
          
    #  get_order_history 
       
    @staticmethod
    async def get_order_history(
        upstox_user_id: str,
        db: Session,
        order_id: str | None = None,
        tag: str | None = None,
    ) -> dict:
        """
        Get order history from Upstox using order_id and/or tag.
        Save the Upstox response to matching local records in
        order_trading and multi_order_trading.
        """

        # 1. At least one filter is required.
        if order_id is None and tag is None:
            raise HTTPException(
                status_code=422,
                detail="Provide at least one of order_id or tag.",
            )

        if order_id is not None:
            order_id = order_id.strip()
            if not order_id:
                raise HTTPException(
                    status_code=422,
                    detail="order_id cannot be empty.",
                )

        if tag is not None:
            tag = tag.strip()
            if not tag:
                raise HTTPException(
                    status_code=422,
                    detail="tag cannot be empty.",
                )

        # 2. Find matching records belonging to this user.
        single_query = db.query(OrderTrading).filter(
            OrderTrading.upstox_user_id == upstox_user_id
        )
        multi_query = db.query(MultiOrderTrading).filter(
            MultiOrderTrading.upstox_user_id == upstox_user_id
        )

        if order_id is not None:
            single_query = single_query.filter(
                OrderTrading.upstox_order_id == order_id
            )
            multi_query = multi_query.filter(
                MultiOrderTrading.upstox_order_id == order_id
            )

        if tag is not None:
            single_query = single_query.filter(
                OrderTrading.tag == tag
            )
            multi_query = multi_query.filter(
                MultiOrderTrading.tag == tag
            )

        single_records = single_query.all()
        multi_records = multi_query.all()

        # 3. Get saved access token.
        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        # 4. Read URL from .env settings.
        url = order_trading_settings.UPSTOX_ORDER_HISTORY_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 5. Send only provided query parameters.
        params = {}

        if order_id is not None:
            params["order_id"] = order_id

        if tag is not None:
            params["tag"] = tag

        # 6. Call Upstox Order History API.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params=params,
                )

        except httpx.TimeoutException:
            logger.exception(
                "Order history request timed out. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=504,
                detail=(
                    "Order history request timed out. "
                    "Please retry later."
                ),
            )

        except httpx.RequestError:
            logger.exception(
                "Unable to connect to Upstox Order History API. "
                "upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=502,
                detail="Unable to connect to the Upstox API.",
            )

        # 7. Parse Upstox response.
        try:
            response_data = response.json()
        except ValueError:
            response_data = {
                "status": "error",
                "message": "Upstox returned invalid JSON.",
                "raw_response": response.text,
            }

        if not isinstance(response_data, dict):
            response_data = {
                "status": "error",
                "message": "Unexpected response format from Upstox.",
                "raw_response": response_data,
            }

        # 8. Save response to matching local records.
        # On Upstox error, save the error response but preserve
        # the existing local order status.
        matching_records = single_records + multi_records
        database_updated_count = 0
        database_errors = []

        try:
            for record in matching_records:
                try:
                    record.upstox_response = json.dumps(
                        response_data,
                        default=str,
                    )

                    # The API returns history entries in data[].
                    # The final entry represents the latest history
                    # event in the documented response sequence.
                    if response.is_success:
                        history_items = response_data.get("data")

                        if (
                            response_data.get("status") == "success"
                            and isinstance(history_items, list)
                            and history_items
                        ):
                            latest_item = history_items[-1]

                            if isinstance(latest_item, dict):
                                latest_status = latest_item.get("status")

                                if latest_status:
                                    record.status = str(
                                        latest_status
                                    ).upper()

                    database_updated_count += 1

                except Exception as record_error:
                    database_errors.append(str(record_error))
                    logger.exception(
                        "Failed to save order history. upstox_user_id=%s",
                        upstox_user_id,
                    )

            db.commit()

        except Exception:
            db.rollback()
            logger.exception(
                "Order history database synchronization failed. "
                "upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Upstox responded, but saving order history "
                    "to the database failed."
                ),
            )

        # 9. Return Upstox response and local DB details.
        logger.info(
            "Order history processed. upstox_user_id=%s http_status=%s "
            "database_updated_count=%s",
            upstox_user_id,
            response.status_code,
            database_updated_count,
        )

        return {
            "message": (
                "Order history retrieved from Upstox."
                if response.is_success
                else (
                    "Upstox returned an error. Matching local "
                    "records were checked and the response was saved."
                )
            ),
            "upstox_user_id": upstox_user_id,
            "order_id": order_id,
            "tag": tag,
            "upstox_status_code": response.status_code,
            "upstox_success": response.is_success,
            "upstox_response": response_data,
            "database_updated": database_updated_count > 0,
            "database_updated_count": database_updated_count,
            "order_trading_found": len(single_records),
            "multi_order_trading_found": len(multi_records),
            "database_errors": database_errors,
            "database_message": (
                "Matching local records updated with the Upstox response."
                if database_updated_count > 0
                else "No matching local records found in either table."
            ),
        }


# get_order_book

    @staticmethod
    async def get_order_book(
        upstox_user_id: str,
        db: Session,
    ) -> dict:
        """
        Retrieve Upstox order book and synchronize matching
        records from order_trading and multi_order_trading.
        """

        # 1. Fetch local database records.
        try:
            single_records = (
                db.query(OrderTrading)
                .filter(OrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            multi_records = (
                db.query(MultiOrderTrading)
                .filter(MultiOrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

        except Exception:
            db.rollback()
            logger.exception(
                "Failed to fetch local orders. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve local order records.",
            )

        # 2. Serialize local records.
        def serialize_record(record):
            fields = (
                "id",
                "upstox_user_id",
                "upstox_order_id",
                "instrument_token",
                "quantity",
                "product",
                "validity",
                "price",
                "order_type",
                "transaction_type",
                "tag",
                "status",
                "upstox_response",
            )

            result = {}

            for field in fields:
                value = getattr(record, field, None)

                if field == "upstox_response" and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (ValueError, TypeError):
                        pass

                result[field] = value

            return result

        local_data = {
            "order_trading": [
                serialize_record(record)
                for record in single_records
            ],
            "multi_order_trading": [
                serialize_record(record)
                for record in multi_records
            ],
        }

        # 3. Get the saved access token.
        try:
            access_token = OrderTradingService.get_access_token(
                upstox_user_id=upstox_user_id,
                db=db,
            )
        except HTTPException as exc:
            return {
                "message": "Unable to retrieve Upstox access token.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "error": exc.detail,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }
        except Exception as exc:
            logger.exception(
                "Access token retrieval failed. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to retrieve Upstox access token.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "error": str(exc),
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        if not access_token:
            return {
                "message": "Access token not found for this user.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 4. Get the URL from .env settings.
        url = order_trading_settings.UPSTOX_ORDER_BOOK_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        # 5. Call Upstox Order Book API.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                )

        except httpx.TimeoutException:
            logger.exception(
                "Order book request timed out. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Upstox order book request timed out.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        except httpx.RequestError as exc:
            logger.exception(
                "Upstox connection failed. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to connect to Upstox.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "error": str(exc),
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 6. Parse the API response.
        try:
            response_data = response.json()
        except ValueError:
            response_data = {
                "message": "Upstox returned an invalid JSON response.",
                "raw_response": response.text,
            }

        # 7. Return the real Upstox error and local DB data.
        if not response.is_success:
            return {
                "message": "Upstox order book request failed.",
                "upstox_user_id": upstox_user_id,
                "upstox_status_code": response.status_code,
                "upstox_success": False,
                "upstox_response": response_data,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 8. Support list and dictionary response formats.
        if isinstance(response_data, list):
            orders = response_data

        elif isinstance(response_data, dict):
            orders = response_data.get("data")

            if not isinstance(orders, list):
                nested = response_data.get("detail")

                if isinstance(nested, dict):
                    nested_response = nested.get("upstox_response")

                    if isinstance(nested_response, list):
                        orders = nested_response
                    elif isinstance(nested_response, dict):
                        orders = nested_response.get("data")

        else:
            orders = None

        if not isinstance(orders, list):
            return {
                "message": "Unexpected response format from Upstox.",
                "upstox_user_id": upstox_user_id,
                "upstox_status_code": response.status_code,
                "upstox_success": False,
                "upstox_response": response_data,
                "database_data": local_data,
                "database_updated": False,
                "database_updated_count": 0,
            }

        # 9. Index local records by Upstox order ID.
        single_by_id = {}
        multi_by_id = {}

        for record in single_records:
            order_id = getattr(record, "upstox_order_id", None)

            if order_id:
                single_by_id.setdefault(str(order_id), []).append(record)

        for record in multi_records:
            order_id = getattr(record, "upstox_order_id", None)

            if order_id:
                multi_by_id.setdefault(str(order_id), []).append(record)

        updated_single = 0
        updated_multi = 0

        # 10. Update matching records only.
        try:
            for order in orders:
                if not isinstance(order, dict):
                    continue

                order_id = order.get("order_id")

                if not order_id:
                    continue

                order_id = str(order_id)

                for record in single_by_id.get(order_id, []):
                    if order.get("status"):
                        record.status = str(order["status"]).upper()

                    record.upstox_response = json.dumps(
                        order,
                        default=str,
                    )
                    updated_single += 1

                for record in multi_by_id.get(order_id, []):
                    if order.get("status"):
                        record.status = str(order["status"]).upper()

                    record.upstox_response = json.dumps(
                        order,
                        default=str,
                    )
                    updated_multi += 1

            db.commit()

        except Exception:
            db.rollback()
            logger.exception(
                "Order book synchronization failed. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Upstox response was received, but database "
                    "synchronization failed."
                ),
            )

        # 11. Read the latest saved database records.
        single_records = (
            db.query(OrderTrading)
            .filter(OrderTrading.upstox_user_id == upstox_user_id)
            .all()
        )

        multi_records = (
            db.query(MultiOrderTrading)
            .filter(MultiOrderTrading.upstox_user_id == upstox_user_id)
            .all()
        )

        local_data = {
            "order_trading": [
                serialize_record(record)
                for record in single_records
            ],
            "multi_order_trading": [
                serialize_record(record)
                for record in multi_records
            ],
        }

        updated_count = updated_single + updated_multi

        # 12. Return Upstox data and local database data.
        return {
            "message": "Order book retrieved successfully.",
            "upstox_user_id": upstox_user_id,
            "upstox_status_code": response.status_code,
            "upstox_success": True,
            "upstox_order_count": len(orders),
            "upstox_response": orders,
            "database_data": local_data,
            "database_updated": updated_count > 0,
            "database_updated_count": updated_count,
            "order_trading_updated_count": updated_single,
            "multi_order_trading_updated_count": updated_multi,
        }
        
        
#    get_trades_for_day 
   
    @staticmethod
    async def get_trades_for_day(
        upstox_user_id: str,
        db: Session,
    ) -> dict:

        # 1. Fetch database records for this user.
        try:
            single_records = (
                db.query(OrderTrading)
                .filter(OrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            multi_records = (
                db.query(MultiOrderTrading)
                .filter(MultiOrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

        except Exception:
            db.rollback()
            logger.exception(
                "Failed to fetch database orders. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve database order counts.",
            )

        # 2. Count records from both tables.
        database_order_trading_count = len(single_records)
        database_multi_order_trading_count = len(multi_records)

        database_total_order_count = (
            database_order_trading_count
            + database_multi_order_trading_count
        )

        # 3. Get saved Upstox access token.
        try:
            access_token = OrderTradingService.get_access_token(
                upstox_user_id=upstox_user_id,
                db=db,
            )
        except Exception as exc:
            logger.exception(
                "Failed to retrieve access token. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to retrieve Upstox access token.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "error": str(exc),
                "database_order_trading_count": database_order_trading_count,
                "database_multi_order_trading_count": database_multi_order_trading_count,
                "database_total_order_count": database_total_order_count,
            }

        if not access_token:
            return {
                "message": "Access token not found for this user.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "database_order_trading_count": database_order_trading_count,
                "database_multi_order_trading_count": database_multi_order_trading_count,
                "database_total_order_count": database_total_order_count,
            }

        # 4. Get URL from existing settings.
        url = order_trading_settings.UPSTOX_GET_TRADES_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 5. Call Upstox Get Trades API.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                )

        except httpx.RequestError as exc:
            logger.exception(
                "Upstox Get Trades request failed. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to connect to Upstox.",
                "upstox_user_id": upstox_user_id,
                "upstox_success": False,
                "error": str(exc),
                "database_order_trading_count": database_order_trading_count,
                "database_multi_order_trading_count": database_multi_order_trading_count,
                "database_total_order_count": database_total_order_count,
            }

        # 6. Parse actual Upstox response.
        try:
            upstox_response = response.json()
        except ValueError:
            upstox_response = {
                "raw_response": response.text,
            }

        # 7. Return actual Upstox API errors.
        if not response.is_success:
            return {
                "message": "Upstox Get Trades request failed.",
                "upstox_user_id": upstox_user_id,
                "upstox_status_code": response.status_code,
                "upstox_success": False,
                "upstox_response": upstox_response,
                "database_order_trading_count": database_order_trading_count,
                "database_multi_order_trading_count": database_multi_order_trading_count,
                "database_total_order_count": database_total_order_count,
            }

        # 8. Extract trades returned by Upstox.
        trades = []

        if isinstance(upstox_response, dict):
            data = upstox_response.get("data", [])

            if isinstance(data, list):
                trades = data

        # 9. Return Upstox data and database counts only.
        return {
            "message": "Upstox trades retrieved successfully.",
            "upstox_user_id": upstox_user_id,
            "upstox_status_code": response.status_code,
            "upstox_success": (
                isinstance(upstox_response, dict)
                and upstox_response.get("status") == "success"
            ),
            "upstox_trade_count": len(trades),
            "upstox_response": upstox_response,
            "database_order_trading_count": database_order_trading_count,
            "database_multi_order_trading_count": database_multi_order_trading_count,
            "database_total_order_count": database_total_order_count,
        }
        
         
    #   get_order_trades   
        
    @staticmethod
    async def get_order_trades(
        upstox_user_id: str,
        order_id: str,
        db: Session,
    ) -> dict:
        """
        Retrieve executed trades for a specific Upstox order.
        Documentation endpoint: GET /v2/order/trades?order_id=...
        """

        # 1. Verify that the order belongs to this user.
        try:
            single_order = (
                db.query(OrderTrading)
                .filter(
                    OrderTrading.upstox_user_id == upstox_user_id,
                    OrderTrading.upstox_order_id == order_id,
                )
                .first()
            )

            multi_order = (
                db.query(MultiOrderTrading)
                .filter(
                    MultiOrderTrading.upstox_user_id == upstox_user_id,
                    MultiOrderTrading.upstox_order_id == order_id,
                )
                .first()
            )

        except Exception:
            db.rollback()
            logger.exception(
                "Failed to fetch order. upstox_user_id=%s order_id=%s",
                upstox_user_id,
                order_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve order from database.",
            )

        if not single_order and not multi_order:
            raise HTTPException(
                status_code=404,
                detail="Order not found for this user.",
            )

        # 2. Get the user's saved access token.
        try:
            access_token = OrderTradingService.get_access_token(
                upstox_user_id=upstox_user_id,
                db=db,
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception(
                "Access token retrieval failed. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve Upstox access token.",
            )

        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="Access token not found for this user.",
            )

        # 3. Get the endpoint from existing settings.
        url = order_trading_settings.UPSTOX_GET_TRADES_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # 4. Call the documented API with required order_id.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params={"order_id": order_id},
                )

        except httpx.TimeoutException:
            logger.exception(
                "Get Order Trades timed out. upstox_user_id=%s order_id=%s",
                upstox_user_id,
                order_id,
            )
            raise HTTPException(
                status_code=504,
                detail="Upstox Get Order Trades request timed out.",
            )

        except httpx.RequestError:
            logger.exception(
                "Get Order Trades connection failed. "
                "upstox_user_id=%s order_id=%s",
                upstox_user_id,
                order_id,
            )
            raise HTTPException(
                status_code=502,
                detail="Unable to connect to Upstox.",
            )

        # 5. Parse the Upstox response.
        try:
            upstox_response = response.json()
        except ValueError:
            upstox_response = {
                "raw_response": response.text,
            }

        # 6. Handle Upstox API errors.
        if not response.is_success:
            return {
                "message": "Upstox Get Order Trades request failed.",
                "upstox_user_id": upstox_user_id,
                "order_id": order_id,
                "upstox_status_code": response.status_code,
                "upstox_success": False,
                "upstox_response": upstox_response,
            }

        # 7. Extract trades according to the documentation.
        api_success = (
            isinstance(upstox_response, dict)
            and upstox_response.get("status") == "success"
        )

        trades = []

        if api_success:
            data = upstox_response.get("data", [])

            if isinstance(data, list):
                trades = data
            else:
                api_success = False

        # 8. Return the trades.
        return {
            "message": (
                "Order trades retrieved successfully."
                if api_success
                else "Unable to retrieve order trades successfully."
            ),
            "upstox_user_id": upstox_user_id,
            "order_id": order_id,
            "upstox_status_code": response.status_code,
            "upstox_success": api_success,
            "upstox_trade_count": len(trades),
            "upstox_response": upstox_response,
        }


# get_trade_history 
 
    @staticmethod
    async def get_trade_history(
        upstox_user_id: str,
        start_date: str,
        end_date: str,
        page_number: int,
        page_size: int,
        db: Session,
        segment: str | None = None,
    ) -> dict:
        """Get segment-specific Upstox trade history and local orders."""

        import json
        from datetime import datetime

        # 1. Validate dates.
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Dates must use YYYY-MM-DD format.",
            )

        if end < start:
            raise HTTPException(
                status_code=400,
                detail="end_date must be >= start_date.",
            )

        if page_number < 1:
            raise HTTPException(
                status_code=400,
                detail="page_number must be at least 1.",
            )

        if not 1 <= page_size <= 5000:
            raise HTTPException(
                status_code=400,
                detail="page_size must be between 1 and 5000.",
            )

        valid_segments = {"EQ", "FO", "COM", "CD", "MF"}

        if segment is not None:
            segment = segment.upper()

            if segment not in valid_segments:
                raise HTTPException(
                    status_code=400,
                    detail="segment must be EQ, FO, COM, CD, or MF.",
                )

        # 2. Identify the segment of a local order.
        def identify_segment(record):
            token = str(
                getattr(record, "instrument_token", "") or ""
            ).upper()

            saved_response = getattr(record, "upstox_response", None)

            if isinstance(saved_response, str):
                try:
                    saved_response = json.loads(saved_response)
                except (ValueError, TypeError):
                    saved_response = {}

            if not isinstance(saved_response, dict):
                saved_response = {}

            # Prefer explicit segment information when available.
            response_segment = str(
                saved_response.get("segment", "")
            ).upper()

            if response_segment in valid_segments:
                return response_segment

            # Identify from the instrument token.
            token_prefixes = {
                "_EQ|": "EQ",
                "_FO|": "FO",
                "_COM|": "COM",
                "_CD|": "CD",
                "_MF|": "MF",
            }

            for prefix, detected_segment in token_prefixes.items():
                if prefix in token:
                    return detected_segment

            # Use exchange information if available.
            exchange = str(
                saved_response.get("exchange", "")
            ).upper()

            exchange_segments = {
                "NFO": "FO",
                "BFO": "FO",
                "MCX": "COM",
                "BCD": "CD",
                "CDS": "CD",
            }

            if exchange in exchange_segments:
                return exchange_segments[exchange]

            return None

        # 3. Fetch local orders for this user.
        try:
            single_records = (
                db.query(OrderTrading)
                .filter(OrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

            multi_records = (
                db.query(MultiOrderTrading)
                .filter(MultiOrderTrading.upstox_user_id == upstox_user_id)
                .all()
            )

        except Exception:
            db.rollback()
            logger.exception(
                "Failed to fetch local orders. upstox_user_id=%s",
                upstox_user_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Unable to retrieve local database orders.",
            )

        # 4. Filter BOTH tables by the selected segment.
        if segment is not None:
            single_records = [
                record for record in single_records
                if identify_segment(record) == segment
            ]

            multi_records = [
                record for record in multi_records
                if identify_segment(record) == segment
            ]

        def serialize_record(record):
            fields = (
                "id",
                "upstox_user_id",
                "upstox_order_id",
                "instrument_token",
                "quantity",
                "product",
                "validity",
                "price",
                "order_type",
                "transaction_type",
                "tag",
                "status",
                "upstox_response",
            )

            result = {}

            for field in fields:
                value = getattr(record, field, None)

                if field == "upstox_response" and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (ValueError, TypeError):
                        pass

                result[field] = value

            result["segment"] = identify_segment(record)
            return result

        # 5. Build segment-specific database response.
        database_data = {
            "order_trading": [
                serialize_record(record)
                for record in single_records
            ],
            "multi_order_trading": [
                serialize_record(record)
                for record in multi_records
            ],
        }

        database_counts = {
            "database_order_trading_count": len(single_records),
            "database_multi_order_trading_count": len(multi_records),
            "database_total_order_count": (
                len(single_records) + len(multi_records)
            ),
            "database_data": database_data,
        }

        # 6. Get this user's saved access token.
        try:
            access_token = OrderTradingService.get_access_token(
                upstox_user_id=upstox_user_id,
                db=db,
            )
        except HTTPException as exc:
            return {
                "message": "Unable to retrieve Upstox access token.",
                "upstox_user_id": upstox_user_id,
                "segment": segment,
                "upstox_success": False,
                "error": exc.detail,
                "upstox_trades": [],
                **database_counts,
            }
        except Exception:
            logger.exception(
                "Access token retrieval failed. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to retrieve Upstox access token.",
                "upstox_user_id": upstox_user_id,
                "segment": segment,
                "upstox_success": False,
                "upstox_trades": [],
                **database_counts,
            }

        if not access_token:
            return {
                "message": "Access token not found for this user.",
                "upstox_user_id": upstox_user_id,
                "segment": segment,
                "upstox_success": False,
                "upstox_trades": [],
                **database_counts,
            }

        # 7. Prepare the documented historical trades request.
        url = order_trading_settings.UPSTOX_HISTORICAL_TRADES_URL

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        params = {
            "start_date": start_date,
            "end_date": end_date,
            "page_number": page_number,
            "page_size": page_size,
        }

        # Pass ONLY the requested segment to Upstox.
        if segment is not None:
            params["segment"] = segment

        # 8. Call Upstox.
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params=params,
                )

        except httpx.TimeoutException:
            logger.exception(
                "Historical trades timed out. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Upstox request timed out; local data is included.",
                "upstox_user_id": upstox_user_id,
                "segment": segment,
                "upstox_success": False,
                "upstox_trades": [],
                **database_counts,
            }

        except httpx.RequestError:
            logger.exception(
                "Historical trades connection failed. upstox_user_id=%s",
                upstox_user_id,
            )
            return {
                "message": "Unable to connect to Upstox; local data is included.",
                "upstox_user_id": upstox_user_id,
                "segment": segment,
                "upstox_success": False,
                "upstox_trades": [],
                **database_counts,
            }

        # 9. Parse Upstox response.
        try:
            upstox_response = response.json()
        except ValueError:
            upstox_response = {"raw_response": response.text}

        if not response.is_success:
            return {
                "message": "Upstox historical trades request failed.",
                "upstox_user_id": upstox_user_id,
                "segment": segment,
                "upstox_status_code": response.status_code,
                "upstox_success": False,
                "upstox_trades": [],
                "upstox_response": upstox_response,
                **database_counts,
            }

        # 10. Extract trades and enforce the requested segment.
        api_success = (
            isinstance(upstox_response, dict)
            and upstox_response.get("status") == "success"
        )

        trades = []
        meta_data = None

        if isinstance(upstox_response, dict):
            data = upstox_response.get("data", [])

            if isinstance(data, list):
                trades = data
            else:
                api_success = False

            meta_data = upstox_response.get("meta_data")
        else:
            api_success = False

        # Defensive filter: never return trades from other segments.
        if segment is not None:
            trades = [
                trade for trade in trades
                if isinstance(trade, dict)
                and str(trade.get("segment", "")).upper() == segment
            ]

        # 11. Return selected-segment trades and selected-segment DB rows.
        return {
            "message": (
                "Trade history retrieved successfully."
                if api_success
                else "Upstox did not return a successful response."
            ),
            "upstox_user_id": upstox_user_id,
            "segment": segment,
            "start_date": start_date,
            "end_date": end_date,
            "page_number": page_number,
            "page_size": page_size,
            "upstox_status_code": response.status_code,
            "upstox_success": api_success,
            "upstox_trade_count": len(trades),
            "upstox_trades": trades,
            "meta_data": meta_data,
            **database_counts,
        }
