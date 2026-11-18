import requests
from sqlalchemy.orm import Session
from config.order_trading_config import order_trading_settings
from services.order_trading_service import OrderTradingService


class IPOOrdersService:

# Get_ipos

    @staticmethod
    def get_ipos(
        upstox_user_id: str,
        db: Session,
        status: str = "open",
        issue_type: str | None = None,
        page_number: int = 1,
        records: int = 20,
    ):
        # 1. Existing user ka saved Upstox access token lo
        access_token = OrderTradingService.get_access_token(
            upstox_user_id=upstox_user_id,
            db=db,
        )

        if not access_token:
            return {
                "status": "error",
                "message": "Access token not found for this user",
            }

        # 2. Upstox API ke query parameters
        params = {
            "status": status,
            "page_number": page_number,
            "records": records,
        }

        if issue_type is not None:
            params["issue_type"] = issue_type

        # 3. Upstox API call
        try:
            response = requests.get(
                order_trading_settings.UPSTOX_IPO_LIST_URL,
                params=params,
                headers={
                    "Accept": "application/json",
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

            # 4. Upstox ka actual response check karo
            if (
                response.ok
                and response_data.get("status") == "success"
            ):
                return {
                    "status": "success",
                    "upstox_user_id": upstox_user_id,
                    "filters": params,
                    "data": response_data.get("data", []),
                    "meta_data": response_data.get("meta_data"),
                }

            return {
                "status": "failed",
                "upstox_user_id": upstox_user_id,
                "upstox_http_status": response.status_code,
                "data": response_data,
            }

        except requests.RequestException as exc:
            return {
                "status": "error",
                "message": "Unable to fetch IPO list from Upstox",
                "error": str(exc),
            }
