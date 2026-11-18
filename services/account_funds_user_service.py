import requests
from sqlalchemy.orm import Session
from models.upstox_user_login import (
    AccessToken
)
from config.account_funds_user_config import (
    account_funds_settings
)


class AccountFundsUserService:

# Get profile 

    @staticmethod
    def get_profile(
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
                "message": "User not found"
            }

        response = requests.get(
            account_funds_settings.UPSTOX_PROFILE_URL,
            headers={
                "Accept": "application/json",
                "Authorization":
                    f"Bearer {token_row.access_token}"
            }
        )

        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": response.json()
        }
    
        
#   Get Funds and Margin V3
      
    @staticmethod
    def get_funds_and_margin(
        db: Session,
        upstox_user_id: str
    ):

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

        headers = {
            "Accept": "application/json",
            "Api-Version": "3.0",
            "Authorization":
                f"Bearer {access_token_row.access_token}"
        }

        try:

            response = requests.get(
                url=(
                    account_funds_settings
                    .UPSTOX_FUNDS_MARGIN_URL
                ),
                headers=headers,
                timeout=30
            )

            response_json = (
                response.json()
            )

            return {
                "success":
                    response.status_code == 200,

                "status_code":
                    response.status_code,

                "response":
                    response_json
            }

        except requests.exceptions.RequestException as e:

            return {
                "success": False,
                "message":
                    f"Request Error: {str(e)}"
            }

        except Exception as e:

            return {
                "success": False,
                "message":
                    f"Unexpected Error: {str(e)}"
            }
            
                
    # Update_kill_switch
    
    @staticmethod
    def update_kill_switch(
        db: Session,
        upstox_user_id: str,
        updates: list
    ):

        access_token_row = (
            db.query(
                AccessToken
            )
            .filter(
                AccessToken.upstox_user_id
                == upstox_user_id
            )
            .first()
        )

        if not access_token_row:

            return {
                "success": False,
                "message":
                    "Please login first"
            }

        headers = {
            "Accept":
                "application/json",

            "Content-Type":
                "application/json",

            "Authorization":
                f"Bearer "
                f"{access_token_row.access_token}"
        }

        payload = []

        for item in updates:

            action = (
                item.action
                .strip()
                .upper()
            )

            if action == "E":

                action = "ENABLE"

            elif action == "D":

                action = "DISABLE"

            else:

                return {
                    "success": False,
                    "message":
                        "Invalid action. Use E or D"
                }

            payload.append(
                {
                    "segment":
                        item.segment
                        .strip()
                        .upper(),

                    "action":
                        action
                }
            )

        try:

            response = requests.post(
                url=(
                    account_funds_settings
                    .UPSTOX_KILL_SWITCH_URL
                ),
                headers=headers,
                json=payload,
                timeout=30
            )

            response_json = (
                response.json()
            )

            if response.status_code != 200:

                return {
                    "success": False,
                    "status_code":
                        response.status_code,
                    "response":
                        response_json
                }

            disabled_segments = []

            for item in response_json.get(
                "data",
                []
            ):

                if item.get(
                    "kill_switch_enabled"
                ) is True:

                    disabled_segments.append(
                        {
                            "segment":
                                item.get(
                                    "segment"
                                ),
                            "segment_status":
                                item.get(
                                    "segment_status"
                                ),
                            "kill_switch_enabled":
                                item.get(
                                    "kill_switch_enabled"
                                )
                        }
                    )

            return {
                "success": True,
                "status_code": 200,
                "data":
                    disabled_segments
            }

        except requests.exceptions.RequestException as e:

            return {
                "success": False,
                "message":
                    f"Request Error: {str(e)}"
            }

        except Exception as e:

            return {
                "success": False,
                "message":
                    f"Unexpected Error: {str(e)}"
            }
        
                 
#   Kill Switch Status  
         
    @staticmethod
    def get_kill_switch_status(
        db: Session,
        upstox_user_id: str
    ):

        access_token_row = (
            db.query(
                AccessToken
            )
            .filter(
                AccessToken.upstox_user_id
                == upstox_user_id
            )
            .first()
        )

        if not access_token_row:

            return {
                "success": False,
                "message":
                    "Please login first"
            }

        headers = {
            "Accept":
                "application/json",

            "Authorization":
                f"Bearer "
                f"{access_token_row.access_token}"
        }

        try:

            response = requests.get(
                url=(
                    account_funds_settings
                    .UPSTOX_KILL_SWITCH_URL
                ),
                headers=headers,
                timeout=30
            )

            response_json = (
                response.json()
            )

            if response.status_code != 200:

                return {
                    "success": False,
                    "status_code":
                        response.status_code,
                    "response":
                        response_json
                }

            enabled_segments = []

            for item in response_json.get(
                "data",
                []
            ):

                if item.get(
                    "kill_switch_enabled"
                ) is True:

                    enabled_segments.append(
                        item
                    )

            if not enabled_segments:

                return {
                    "success": True,
                    "status_code": 200,
                    "message":
                        "No segment has kill switch enabled",
                    "data": []
                }

            return {
                "success": True,
                "status_code": 200,
                "data":
                    enabled_segments
            }

        except requests.exceptions.RequestException as e:

            return {
                "success": False,
                "message":
                    f"Request Error: {str(e)}"
            }

        except Exception as e:

            return {
                "success": False,
                "message":
                    f"Unexpected Error: {str(e)}"
            }
      
    
#  Get Static Ip    
      
    @staticmethod
    def get_static_ips(
        db: Session,
        upstox_user_id: str
    ):
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

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": (
                f"Bearer {access_token_row.access_token}"
            )
        }

        try:
            response = requests.get(
                url=account_funds_settings.UPSTOX_STATIC_IP_URL,
                headers=headers,
                timeout=30
            )

            response_json = response.json()

            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response_json
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"Request Error: {str(e)}"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected Error: {str(e)}"
            }
   
                            
# Update Static Ip       
            
    @staticmethod
    def update_static_ips(
        db: Session,
        upstox_user_id: str,
        primary_ip: str,
        secondary_ip: str = None
    ):

        access_token_row = (
            db.query(
                AccessToken
            )
            .filter(
                AccessToken.upstox_user_id
                == upstox_user_id
            )
            .first()
        )

        if not access_token_row:

            return {
                "success": False,
                "message":
                    "Please login first"
            }

        headers = {
            "Accept":
                "application/json",

            "Content-Type":
                "application/json",

            "Authorization":
                f"Bearer "
                f"{access_token_row.access_token}"
        }

        payload = {
            "primary_ip":
                primary_ip
        }

        if secondary_ip:

            payload[
                "secondary_ip"
            ] = secondary_ip

        try:

            response = requests.put(
                url=(
                    account_funds_settings
                    .UPSTOX_STATIC_IP_URL
                ),
                headers=headers,
                json=payload,
                timeout=30
            )

            response_json = (
                response.json()
            )

            return {
                "success":
                    response.status_code == 200,

                "status_code":
                    response.status_code,

                "response":
                    response_json
            }

        except requests.exceptions.RequestException as e:

            return {
                "success": False,
                "message":
                    f"Request Error: {str(e)}"
            }

        except Exception as e:

            return {
                "success": False,
                "message":
                    f"Unexpected Error: {str(e)}"
            }
            