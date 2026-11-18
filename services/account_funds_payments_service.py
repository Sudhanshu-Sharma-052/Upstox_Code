import requests
from sqlalchemy.orm import Session
from models.upstox_user_login import (
    AccessToken,
    UpstoxUserLogin
)
from config.account_funds_user_config import (
    account_funds_settings
)


class AccountFundsPaymentsService:
     
       
# Payments        
        
    @staticmethod
    def get_payins(
        db: Session,
        upstox_user_id: str
    ):

        user = (
            db.query(UpstoxUserLogin)
            .filter(
                UpstoxUserLogin.upstox_user_id == upstox_user_id
            )
            .first()
        )

        if not user:

            return {
                "success": False,
                "message": "User not found"
            }

        access_token_row = (
            db.query(AccessToken)
            .filter(
                AccessToken.upstox_user_id == upstox_user_id
            )
            .first()
        )

        if not access_token_row:

            return {
                "success": False,
                "message": "Please login first"
            }

        response = requests.get(
            account_funds_settings.UPSTOX_PAYINS_URL,
            headers={
                "accept": "application/json",
                "Authorization":
                    f"Bearer {access_token_row.access_token}"
            }
        )

        try:

            data = response.json()

        except Exception:

            return {
                "success": False,
                "message": response.text
            }

        if response.status_code != 200:

            errors = data.get(
                "errors",
                []
            )

            if errors:

                error_code = (
                    errors[0]
                    .get("error_code")
                    or
                    errors[0]
                    .get("errorCode")
                )

                if (
                    error_code
                    == "UDAPI100050"
                ):

                    return {
                        "success": False,
                        "message":
                            "Session expired. Please login again"
                    }

            return data

        return {
            "status": data.get(
                "status",
                "success"
            ),
            "data": data.get(
                "data",
                []
            )
        }
        
        
    # Get_payouts 
        
    @staticmethod
    def get_payouts(
        db: Session,
        upstox_user_id: str
    ):

        token_row = (
            db.query(AccessToken)
            .filter(
                AccessToken.upstox_user_id == upstox_user_id
            )
            .first()
        )

        if not token_row:

            return {
                "success": False,
                "message": "Access token not found"
            }

        response = requests.get(
            account_funds_settings.UPSTOX_PAYOUT_URL,
            headers={
                "Accept":
                    "application/json",
                "Authorization":
                    f"Bearer {token_row.access_token}"
            }
        )

        return {
            "success":
                response.status_code == 200,
            "status_code":
                response.status_code,
            "response":
                response.json()
        }
        
        
    #  Get_payout_modes 
       
    @staticmethod
    def get_payout_modes(
        db: Session,
        upstox_user_id: str
    ):

        token_row = (
            db.query(AccessToken)
            .filter(
                AccessToken.upstox_user_id == upstox_user_id
            )
            .first()
        )

        if not token_row:

            return {
                "success": False,
                "message": "Token not found"
            }

        response = requests.get(
            account_funds_settings.UPSTOX_PAYOUT_MODES_URL,
            headers={
                "Accept":
                    "application/json",
                "Authorization":
                    f"Bearer {token_row.access_token}"
            }
        )

        return {
            "success":
                response.status_code == 200,
            "status_code":
                response.status_code,
            "response":
                response.json()
        }    
        
         
    #   Payout_request  
        
    @staticmethod
    def payout_request(
        db: Session,
        upstox_user_id: str,
        mode: str,
        amount: float
    ):

        token_row = (
            db.query(AccessToken)
            .filter(
                AccessToken.upstox_user_id == upstox_user_id
            )
            .first()
        )

        if not token_row:

            return {
                "success": False,
                "message": "Token not found"
            }

        response = requests.post(
            account_funds_settings
            .UPSTOX_PAYOUT_REQUEST_URL,
            headers={
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
                "Authorization":
                    f"Bearer {token_row.access_token}"
            },
            json={
                "mode": mode,
                "amount": amount
            }
        )

        try:

            data = (
                response.json()
            )

        except Exception:

            data = {
                "response":
                    response.text
            }

        return {
            "success":
                response.status_code == 200,
            "status_code":
                response.status_code,
            "response":
                data
        } 
        
     
    #   Modify_payout 
        
    @staticmethod
    def modify_payout(
        db: Session,
        upstox_user_id: str,
        transaction_id: str,
        amount: float
    ):

        token_row = (
            db.query(AccessToken)
            .filter(
                AccessToken.upstox_user_id == upstox_user_id
            )
            .first()
        )

        if not token_row:

            return {
                "success": False,
                "message": "Token not found"
            }

        response = requests.put(
            f"{account_funds_settings.UPSTOX_MODIFY_PAYOUT_URL}/{transaction_id}",
            headers={
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
                "Authorization":
                    f"Bearer {token_row.access_token}"
            },
            json={
                "amount": amount
            }
        )

        try:

            data = (
                response.json()
            )

        except Exception:

            data = {
                "response":
                    response.text
            }

        return {
            "success":
                response.status_code == 200,
            "status_code":
                response.status_code,
            "response":
                data
        }  
        
        
    #  Cancel_payout
        
    @staticmethod
    def cancel_payout(
        db: Session,
        upstox_user_id: str,
        transaction_id: str
    ):

        access_token_row = (
            db.query(AccessToken)
            .filter_by(
                upstox_user_id=upstox_user_id
            )
            .first()
        )

        if not access_token_row:

            return {
                "success": False,
                "message": "Login first"
            }

        response = requests.delete(
            f"{account_funds_settings.UPSTOX_PAYOUT_URL}/{transaction_id}",
            headers={
                "accept":
                    "application/json",
                "Authorization":
                    f"Bearer {access_token_row.access_token}"
            }
        )

        try:

            data = (
                response.json()
            )

        except Exception:

            data = {
                "response":
                    response.text
            }

        return {
            "success":
                response.status_code == 200,
            "status_code":
                response.status_code,
            "response":
                data
        }
        
   
# Charges 

    @staticmethod
    def get_brokerage(
        db: Session,
        upstox_user_id: str,
        instrument_token: str,
        quantity: int,
        product: str,
        transaction_type: str,
        price: float
    ):

        access_token_row = (
            db.query(AccessToken)
            .filter_by(
                upstox_user_id=upstox_user_id
            )
            .first()
        )

        if not access_token_row:

            return {
                "success": False,
                "message": "Login first"
            }

        response = requests.get(
            account_funds_settings.UPSTOX_BROKERAGE_URL,
            headers={
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
                "Authorization":
                    f"Bearer {access_token_row.access_token}"
            },
            params={
                "instrument_token":
                    instrument_token,
                "quantity":
                    quantity,
                "product":
                    product,
                "transaction_type":
                    transaction_type,
                "price":
                    price
            }
        )

        try:

            data = (
                response.json()
            )

        except Exception:

            data = {
                "response":
                    response.text
            }

        return {
            "success":
                response.status_code == 200,
            "status_code":
                response.status_code,
            "response":
                data
        }        
        
        
# Margins 

    @staticmethod
    def get_margin(
        db: Session,
        upstox_user_id: str,
        instruments: list
    ):

        access_token_row = (
            db.query(AccessToken)
            .filter_by(
                upstox_user_id=upstox_user_id
            )
            .first()
        )

        if not access_token_row:

            return {
                "success": False,
                "message": "Login first"
            }

        payload = {
            "instruments":
                instruments
        }

        response = requests.post(
            account_funds_settings.UPSTOX_MARGIN_URL,
            headers={
                "accept":
                    "application/json",
                "Content-Type":
                    "application/json",
                "Authorization":
                    f"Bearer {access_token_row.access_token}"
            },
            json=payload
        )

        try:

            data = (
                response.json()
            )

        except Exception:

            data = {
                "response":
                    response.text
            }

        return {
            "success":
                response.status_code == 200,
            "status_code":
                response.status_code,
            "response":
                data
        }        