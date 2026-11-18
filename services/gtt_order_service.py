import requests
from sqlalchemy.orm import Session
from config.order_trading_config import order_trading_settings
from models.gtt_order_model import GTTOrder
from schemas.gtt_order_schemas import (
    GTTModifySchema,
    GTTOrderSchema,
    GTTCancelSchema,

)
from services.order_trading_service import OrderTradingService


class GTTOrderService:

    @staticmethod
    def _get_access_token(upstox_user_id: str, db: Session):
        return OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

    @staticmethod
    def _clean_payload(payload: dict) -> dict:
        for rule in payload.get("rules", []):
            strategy = rule.get("strategy")
            gap = rule.get("trailing_gap")

            if strategy != "STOPLOSS":
                rule.pop("trailing_gap", None)
            elif gap == 0:
                rule.pop("trailing_gap", None)

        return payload
    
    
# Place_gtt_order 

    @staticmethod
    def place_gtt_order(
        upstox_user_id: str,
        db: Session,
        order: GTTOrderSchema,
    ):
        access_token = GTTOrderService._get_access_token(upstox_user_id, db)

        if not access_token:
            return {
                "status": "error",
                "message": "Access token not found for this user",
            }

        payload = GTTOrderService._clean_payload(
            order.model_dump(exclude_none=True)
        )

        record = GTTOrder(
            upstox_user_id=upstox_user_id,
            instrument_token=order.instrument_token,
            transaction_type=order.transaction_type,
            order_type=order.type,
            quantity=order.quantity,
            product=order.product,
            request_payload=payload,
            status="PENDING",
        )

        try:
            db.add(record)
            db.commit()
            db.refresh(record)

            response = requests.post(
                order_trading_settings.UPSTOX_GTT_PLACE_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json=payload,
                timeout=30,
            )

            try:
                response_data = response.json()
            except ValueError:
                response_data = {"message": response.text}

            success = (
                response.ok
                and response_data.get("status") == "success"
            )

            record.upstox_response = response_data
            record.status = "SUCCESS" if success else "FAILED"

            if success:
                order_ids = response_data.get(
                    "data", {}
                ).get("gtt_order_ids", [])

                if order_ids:
                    record.gtt_order_id = order_ids[0]

            db.commit()
            db.refresh(record)

            return {
                "status": record.status.lower(),
                "database_id": record.id,
                "gtt_order_id": record.gtt_order_id,
                "upstox_http_status": response.status_code,
                "data": response_data,
            }

        except requests.RequestException as exc:
            try:
                record.status = "FAILED"
                record.upstox_response = {"message": str(exc)}
                db.commit()
            except Exception:
                db.rollback()
                raise

            return {
                "status": "error",
                "database_id": record.id,
                "message": "Upstox API request failed",
            }

        except Exception:
            db.rollback()
            raise


#  Modify_gtt_order

    @staticmethod
    def modify_gtt_order(
        upstox_user_id: str,
        db: Session,
        order: GTTModifySchema,
    ):
        # Fixed: helper method ab isi class mein defined hai.
        access_token = GTTOrderService._get_access_token(upstox_user_id, db)

        if not access_token:
            return {
                "status": "error",
                "message": "Access token not found for this user",
            }

        payload = GTTOrderService._clean_payload(
            order.model_dump(exclude_none=True)
        )

        # Local DB record optional hai; Upstox ID request ke liye required hai.
        record = (
            db.query(GTTOrder)
            .filter(
                GTTOrder.upstox_user_id == upstox_user_id,
                GTTOrder.gtt_order_id == order.gtt_order_id,
            )
            .first()
        )

        try:
            response = requests.put(
                order_trading_settings.UPSTOX_GTT_MODIFY_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json=payload,
                timeout=30,
            )

            try:
                response_data = response.json()
            except ValueError:
                response_data = {"message": response.text}

            success = (
                response.ok
                and response_data.get("status") == "success"
            )

            if record:
                record.request_payload = payload
                record.upstox_response = response_data
                record.status = (
                    "MODIFIED" if success else "LOCAL_MODIFIED"
                )
                record.order_type = order.type
                record.quantity = order.quantity

                returned_ids = response_data.get(
                    "data", {}
                ).get("gtt_order_ids", [])

                if success and returned_ids:
                    record.gtt_order_id = returned_ids[0]

                db.commit()
                db.refresh(record)

            result = {
                "status": (
                    record.status
                    if record
                    else "MODIFIED" if success else "failed"
                ),
                "database_updated": record is not None,
                "gtt_order_id": order.gtt_order_id,
                "upstox_http_status": response.status_code,
                "data": response_data,
            }

            if record:
                result["database_id"] = record.id
                result["local_status"] = record.status

            return result

        except requests.RequestException as exc:
            if record:
                try:
                    record.status = "FAILED"
                    record.upstox_response = {"message": str(exc)}
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

            return {
                "status": "error",
                "gtt_order_id": order.gtt_order_id,
                "message": "Upstox API request failed",
            }

        except Exception:
            db.rollback()
            raise


# Cancel_gtt_order

    @staticmethod
    def cancel_gtt_order(
        upstox_user_id: str,
        db: Session,
        order: GTTCancelSchema,
    ):
        access_token = GTTOrderService._get_access_token(upstox_user_id, db)

        if not access_token:
            return {
                "status": "error",
                "message": "Access token not found for this user",
            }

        # Sirf isi user ka local GTT order find karo.
        record = (
            db.query(GTTOrder)
            .filter(
                GTTOrder.upstox_user_id == upstox_user_id,
                GTTOrder.gtt_order_id == order.gtt_order_id,
            )
            .first()
        )

        if not record:
            return {
                "status": "error",
                "message": "GTT order not found for this user",
                "gtt_order_id": order.gtt_order_id,
            }

        # Already cancelled order ko dobara cancel request mat bhejo.
        if record.status == "CANCELLED":
            return {
                "status": "success",
                "message": "GTT order is already cancelled",
                "database_id": record.id,
                "gtt_order_id": record.gtt_order_id,
                "local_status": record.status,
            }

        payload = {
            "gtt_order_id": order.gtt_order_id,
        }

        try:
            response = requests.delete(
                order_trading_settings.UPSTOX_GTT_CANCEL_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json=payload,
                timeout=30,
            )

            try:
                response_data = response.json()
            except ValueError:
                response_data = {"message": response.text}

            success = (
                response.ok
                and response_data.get("status") == "success"
            )

            record.request_payload = payload
            record.upstox_response = response_data
            record.status = (
                "CANCELLED" if success else "LOCAL_CANCELLED"
            )

            db.commit()
            db.refresh(record)

            return {
                "status": record.status,
                "database_updated": True,
                "database_id": record.id,
                "gtt_order_id": record.gtt_order_id,
                "local_status": record.status,
                "upstox_http_status": response.status_code,
                "data": response_data,
            }

        except requests.RequestException as exc:
            # Timeout/network error ka matlab cancellation confirm nahi hai.
            try:
                record.upstox_response = {
                    "message": str(exc),
                }
                db.commit()
            except Exception:
                db.rollback()
                raise

            return {
                "status": "error",
                "database_id": record.id,
                "gtt_order_id": record.gtt_order_id,
                "local_status": record.status,
                "message": "Upstox cancellation request failed; cancellation is not confirmed",
            }

        except Exception:
            db.rollback()
            raise
         
        
# Get_gtt_order_details

    @staticmethod
    def get_gtt_order_details(
        upstox_user_id: str,
        db: Session,
        gtt_order_id: str | None = None,
    ):
        # 1. User ka saved Upstox access token lo
        access_token = GTTOrderService._get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        if not access_token:
            return {
                "status": "error",
                "message": "Access token not found for this user",
            }

        # 2. Agar specific GTT ID di hai, to user ki local record check karo
        record = None

        if gtt_order_id is not None:
            gtt_order_id = gtt_order_id.strip()

            if not gtt_order_id:
                return {
                    "status": "error",
                    "message": "gtt_order_id cannot be empty",
                }

            record = (
                db.query(GTTOrder)
                .filter(
                    GTTOrder.upstox_user_id == upstox_user_id,
                    GTTOrder.gtt_order_id == gtt_order_id,
                )
                .first()
            )

            if not record:
                return {
                    "status": "error",
                    "message": "GTT order not found for this user",
                    "gtt_order_id": gtt_order_id,
                }

        # 3. Upstox API ke query parameters
        params = {}

        if gtt_order_id:
            params["gtt_order_id"] = gtt_order_id

        # 4. Upstox API call
        try:
            response = requests.get(
                order_trading_settings.UPSTOX_GTT_DETAILS_URL,
                params=params,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=30,
            )

            try:
                response_data = response.json()
            except ValueError:
                response_data = {
                    "message": response.text,
                }

            # 5. Database mein response save karo, agar local order hai
            if record is not None:
                record.upstox_response = response_data

                if (
                    response.ok
                    and response_data.get("status") == "success"
                ):
                    db.commit()
                    db.refresh(record)
                else:
                    db.commit()

            # 6. Final response
            if (
                response.ok
                and response_data.get("status") == "success"
            ):
                return {
                    "status": "success",
                    "upstox_user_id": upstox_user_id,
                    "gtt_order_id": gtt_order_id,
                    "upstox_http_status": response.status_code,
                    "data": response_data.get("data", []),
                    "metadata": response_data.get("metadata"),
                }

            return {
                "status": "failed",
                "upstox_user_id": upstox_user_id,
                "gtt_order_id": gtt_order_id,
                "upstox_http_status": response.status_code,
                "data": response_data,
            }

        except requests.RequestException as exc:
            return {
                "status": "error",
                "message": "Unable to fetch GTT order details from Upstox",
                "error": str(exc),
            }

        except Exception:
            db.rollback()
            raise    
