import logging
import re
import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models.signup_user import User
from config.upstox_login_config import settings

from models.upstox_user_login import (
    UpstoxUserLogin,
    AccessToken,
)

from utils.upstox_login_manager import (
    UpstoxLoginManager
)
logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

def _now_ist_naive():
    return datetime.now(IST).replace(tzinfo=None)

def _as_ist_naive(value):
    if value.tzinfo is not None:
        return value.astimezone(IST).replace(tzinfo=None)
    return value


class UpstoxLoginService:

    # User Signup

    @staticmethod
    def signup(db: Session, payload):

        if (
            not payload.first_name.strip()
            or not payload.last_name.strip()
            or not payload.email.strip()
            or not payload.password.strip()
            or not payload.upstox_user_id.strip()
        ):
            return {
                "message": "Check the credentials carefully"
            }

        email = payload.email.strip().lower()

        email_pattern = (
            r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        )

        if not re.match(email_pattern, email):
            return {
                "message": "Check the credentials carefully"
            }

        upstox_user_id = payload.upstox_user_id.strip()

        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:
            if (
                existing_user.first_name.strip().lower()
                == payload.first_name.strip().lower()
                and existing_user.last_name.strip().lower()
                == payload.last_name.strip().lower()
                and existing_user.password == payload.password
            ):
                return {
                    "message": "User already exists",
                    "upstox_user_id": existing_user.upstox_user_id
                }

            return {
                "message": "Email already registered",
                "upstox_user_id": existing_user.upstox_user_id
            }

        existing_upstox_user = (
            db.query(User)
            .filter(User.upstox_user_id == upstox_user_id)
            .first()
        )

        if existing_upstox_user:
            return {
                "message": "Upstox User ID already registered",
                "upstox_user_id": existing_upstox_user.upstox_user_id
            }

        try:
            client_id = payload.upstox_client_id.strip()
            client_secret = payload.upstox_client_secret.strip()

            if not client_id or not client_secret:
                return {
                    "message": (
                        "Upstox Client ID and Client Secret are required"
                    )
                }

            new_user = User(
                upstox_user_id=upstox_user_id,
                first_name=payload.first_name.strip(),
                last_name=payload.last_name.strip(),
                email=email,
                upstox_client_id=client_id,
                upstox_client_secret=client_secret,
                password=payload.password.strip()
            )

            db.add(new_user)

            db.commit()
            db.refresh(new_user)

            return {
                "message": "Signup successful",
                "upstox_user_id": new_user.upstox_user_id
            }

        except IntegrityError:
            db.rollback()

            existing_upstox_user = (
                db.query(User)
                .filter(User.upstox_user_id == upstox_user_id)
                .first()
            )
            if existing_upstox_user:
                return {
                    "message": "Upstox User ID already registered",
                    "upstox_user_id": existing_upstox_user.upstox_user_id
                }

            existing_email_user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )
            if existing_email_user:
                return {
                    "message": "Email already registered",
                    "upstox_user_id": existing_email_user.upstox_user_id
                }

            logger.exception("Signup failed due to a database constraint")
            return {"message": "Unable to complete signup"}

        except Exception:
            db.rollback()
            logger.exception("Signup failed")

            return {
                "message": "Unable to complete signup"
            }

    
    # forgot_password

    @staticmethod
    def forgot_password(
        db: Session,
        upstox_user_id: str,
        email: str,
        new_password: str
    ):
        upstox_user_id = upstox_user_id.strip()
        email = email.strip().lower()
        new_password = new_password.strip()

        if not upstox_user_id or not email or not new_password:
            return {
                "success": False,
                "message": (
                    "Upstox User ID, email, and new password are required"
                )
            }

        try:
            user = (
                db.query(User)
                .filter(
                    User.upstox_user_id == upstox_user_id,
                    User.email == email
                )
                .first()
            )

            if not user:
                return {
                    "success": False,
                    "message": "Upstox User ID or email does not match"
                }

            user.password = new_password
            db.commit()

            return {
                "success": True,
                "message": "Password updated successfully",
                "upstox_user_id": user.upstox_user_id
            }

        except Exception:
            db.rollback()
            logger.exception(
                "Forgot password failed for upstox_user_id=%s",
                upstox_user_id
            )

            return {
                "success": False,
                "message": "Unable to update password"
            }


    # Login / Authorization
 
    @staticmethod
    def generate_login_url(
        db: Session,
        upstox_user_id: str,
        password: str
    ):
        try:
            upstox_user_id = upstox_user_id.strip()
            password = password.strip()

            user = (
                db.query(User)
                .filter(
                    User.upstox_user_id == upstox_user_id
                )
                .first()
            )

            if not user:
                return {
                    "success": False,
                    "message": "User not found"
                }

            if user.password != password:
                return {
                    "success": False,
                    "message": "Invalid password"
                }

            # API KEY FROM USERS TABLE
            client_id = (
                user.upstox_client_id.strip()
                if user.upstox_client_id else ""
            )

            if not client_id:
                return {
                    "success": False,
                    "message": "Upstox API Key is missing"
                }

            client_id_pattern = (
                r"^[0-9a-fA-F]{8}-"
                r"[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{12}$"
            )
            if not re.fullmatch(client_id_pattern, client_id):
                return {
                    "success": False,
                    "message": (
                        "Stored Upstox Client ID is invalid. Use the API Key "
                        "from your Upstox Developer App."
                    )
                }

            # REGISTERED REDIRECT URI
            redirect_uri = settings.UPSTOX_REDIRECT_URI.strip()

            if not redirect_uri:
                return {
                    "success": False,
                    "message": "Redirect URI is missing"
                }

            redirect_parts = urlsplit(redirect_uri)
            if (
                redirect_parts.scheme not in {"http", "https"}
                or not redirect_parts.netloc
            ):
                return {
                    "success": False,
                    "message": "Redirect URI must be a valid HTTP or HTTPS URL"
                }

            if redirect_parts.path != "/api/upstox/login/callback":
                return {
                    "success": False,
                    "message": (
                        "Redirect URI path must be "
                        "/api/upstox/login/callback"
                    )
                }

            # GENERATE STATE
            state = UpstoxLoginManager.generate_state()

            # SAVE LOGIN RECORD
            token = (
                db.query(UpstoxUserLogin)
                .filter(
                    UpstoxUserLogin.upstox_user_id == upstox_user_id
                )
                .with_for_update()
                .first()
            )

            if token:
                token.upstox_user_id = upstox_user_id
                token.state = state
                token.code = None
            else:
                token = UpstoxUserLogin(
                    upstox_user_id=upstox_user_id,
                    state=state,
                    code=None
                )
                db.add(token)

            db.commit()
            db.refresh(token)

            # GENERATE AUTHORIZATION URL
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "state": state
            }

            login_url = (
                f"{settings.UPSTOX_AUTHORIZE_URL}?"
                f"{urlencode(params)}"
            )

            return {
                "success": True,
                "message": "Login URL generated successfully",
                "upstox_user_id": upstox_user_id,
                "state": state,
                "login_url": login_url
            }

        except Exception:
            db.rollback()

            logger.exception(
                "Failed to generate Upstox login URL"
            )

            return {
                "success": False,
                "message": "Unable to generate login URL"
            }


    # AUTH CALLBACK

    @staticmethod
    def auth_callback(
        db: Session,
        code: str,
        state: str
    ):
        try:

            # VALIDATE INPUT

            code = code.strip() if code else ""
            state = state.strip() if state else ""

            if not code or not state:
                return {
                    "success": False,
                    "message": "Authorization code or state is missing"
                }

            # GET LOGIN RECORD USING STATE

            token = (
                db.query(UpstoxUserLogin)
                .filter(
                    UpstoxUserLogin.state == state
                )
                .with_for_update()
                .first()
            )

            if token is None:
                logger.warning(
                    "Callback state not found"
                )

                return {
                    "success": False,
                    "message": "Authorization code expired"
                }

            if token.code is not None:
                return {
                    "success": False,
                    "message": "Authorization code already received"
                }

            # SAVE AUTHORIZATION CODE

            token.code = code

            db.commit()
            db.refresh(token)

            # VERIFY SAVED CODE

            saved_row = db.execute(
                text("""
                    SELECT
                        id,
                        upstox_user_id,
                        state,
                        code
                    FROM upstox_user_login
                    WHERE upstox_user_id = :upstox_user_id
                    AND state = :state
                """),
                {
                    "upstox_user_id": token.upstox_user_id,
                    "state": state
                }
            ).mappings().first()

            if (
                saved_row is None
                or saved_row["state"] != state
                or saved_row["code"] != code
            ):
                logger.error(
                    "Callback verification failed for upstox_user_id=%s",
                    token.upstox_user_id
                )

                return {
                    "success": False,
                    "message": "Database update verification failed"
                }

            # Exchange the code now so the callback can verify that the
            # authenticated Upstox account matches the locally registered ID.
            token_result = UpstoxLoginService.get_token(
                db=db,
                upstox_user_id=token.upstox_user_id,
            )

            if not token_result.get("success"):
                token.code = None
                token.state = None
                db.commit()
                return token_result

            return {
                "success": True,
                "message": "Upstox account ID verified and access token saved successfully",
                "upstox_user_id": token_result["upstox_user_id"],
                "state": state,
                "code": code,
            }

        except Exception:

            db.rollback()

            logger.exception(
                "Failed to save callback data"
            )

            return {
                "success": False,
                "message": "Failed to save authorization data"
            }


    # GET ACCESS TOKEN

    @staticmethod
    def get_token(
        db: Session,
        upstox_user_id: str
    ):

        try:

            # VALIDATE INPUT

            upstox_user_id = upstox_user_id.strip()

            if not upstox_user_id:
                return {
                    "success": False,
                    "message": "Upstox User ID is required"
                }

            # GET LOGIN RECORD USING UPSTOX USER ID

            token = (
                db.query(UpstoxUserLogin)
                .filter(
                    UpstoxUserLogin.upstox_user_id == upstox_user_id
                )
                .order_by(
                    UpstoxUserLogin.updated_at.desc()
                )
                .with_for_update()
                .first()
            )

            if not token:
                return {
                    "success": False,
                    "message": (
                        "Upstox User ID not found. Access token is unavailable. "
                        "Please sign up first with the correct credentials."
                    )
                }

            # RETURN EXISTING ACCESS TOKEN

            access_token_row = (
                db.query(AccessToken)
                .filter(
                    AccessToken.upstox_user_id == upstox_user_id
                )
                .first()
            )

            if (
                not token.code
                and access_token_row
                and access_token_row.access_token
                and access_token_row.token_expiry_at
                and _now_ist_naive()
                < _as_ist_naive(access_token_row.token_expiry_at)
            ):
                return {
                    "success": True,
                    "upstox_user_id": access_token_row.upstox_user_id,
                    "upstox_user_name": access_token_row.upstox_user_name,
                    "upstox_email": access_token_row.upstox_email,
                    "access_token": access_token_row.access_token,
                    "token_created_at": access_token_row.token_created_at,
                    "token_expiry_at": access_token_row.token_expiry_at
                }

            # CHECK AUTHORIZATION CODE

            if not token.code or token.code.strip() == "":
                return {
                    "success": False,
                    "message": "Login first"
                }

            auth_code = token.code

            # GET CLIENT ID AND SECRET FROM USERS TABLE

            user = (
                db.query(User)
                .filter(
                    User.upstox_user_id == upstox_user_id
                )
                .first()
            )

            if not user:
                return {
                    "success": False,
                    "message": "User not found"
                }

            client_id = (
                user.upstox_client_id.strip()
                if user.upstox_client_id else ""
            )

            client_secret = (
                user.upstox_client_secret.strip()
                if user.upstox_client_secret else ""
            )

            if not client_id or not client_secret:
                return {
                    "success": False,
                    "message": "Upstox client ID or client secret is missing"
                }

            # GET SAME REDIRECT URI USED IN LOGIN URL

            redirect_uri = settings.UPSTOX_REDIRECT_URI.strip()

            if not redirect_uri:
                return {
                    "success": False,
                    "message": "Upstox Redirect URI is missing"
                }

            # REQUEST ACCESS TOKEN FROM UPSTOX

            try:

                response = requests.post(
                    settings.UPSTOX_TOKEN_URL,

                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },

                    data={
                        "code": auth_code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    },

                    timeout=30
                )

                data = response.json()

            except requests.RequestException as e:

                return {
                    "success": False,
                    "message": "Failed to connect to Upstox",
                    "error": str(e)
                }

            except ValueError:

                return {
                    "success": False,
                    "message": "Invalid response received from Upstox"
                }

            if not isinstance(data, dict):
                return {
                    "success": False,
                    "message": "Invalid response received from Upstox"
                }

            # CHECK UPSTOX RESPONSE

            if response.status_code != 200:
                return {
                    "success": False,
                    "message": "Upstox token request failed",
                    "upstox_response": data
                }

            access_token = data.get("access_token")

            if not access_token:
                return {
                    "success": False,
                    "message": "Access token not received from Upstox",
                    "upstox_response": data
                }

            actual_upstox_user_id = data.get("user_id")
            if not isinstance(actual_upstox_user_id, str):
                return {
                    "success": False,
                    "message": "Upstox did not return the authenticated user ID",
                }

            actual_upstox_user_id = actual_upstox_user_id.strip()
            if not actual_upstox_user_id:
                return {
                    "success": False,
                    "message": "Upstox did not return the authenticated user ID",
                }

            if actual_upstox_user_id != upstox_user_id:
                token.code = None
                token.state = None
                db.commit()
                return {
                    "success": False,
                    "message": (
                        "The Upstox account ID does not match the ID "
                        "registered in this account. Correct the registered "
                        "ID and authorize again."
                    ),
                    "expected_upstox_user_id": upstox_user_id,
                    "actual_upstox_user_id": actual_upstox_user_id,
                }

            # TOKEN CREATION AND EXPIRY TIME

            created_at = _now_ist_naive()

            expiry_at = created_at.replace(
                hour=3,
                minute=30,
                second=0,
                microsecond=0
            )

            if created_at >= expiry_at:
                expiry_at = expiry_at + timedelta(days=1)

            # SAVE TOKEN DETAILS IN DATABASE

            try:

                if access_token_row:
                    access_token_row.upstox_user_name = data.get("user_name")
                    access_token_row.upstox_email = data.get("email")
                    access_token_row.access_token = access_token
                    access_token_row.token_created_at = created_at
                    access_token_row.token_expiry_at = expiry_at
                else:
                    access_token_row = AccessToken(
                        upstox_user_id=actual_upstox_user_id,
                        upstox_user_name=data.get("user_name"),
                        upstox_email=data.get("email"),
                        access_token=access_token,
                        token_created_at=created_at,
                        token_expiry_at=expiry_at
                    )
                    db.add(access_token_row)

                token.code = None
                token.state = None
                db.commit()

                db.refresh(access_token_row)

            except Exception as e:

                db.rollback()

                return {
                    "success": False,
                    "message": "Failed to save token details in database",
                    "error": str(e)
                }

            # RETURN SAVED TOKEN DETAILS

            return {
                "success": True,
                "message": "Token generated and saved successfully",
                "upstox_user_id": access_token_row.upstox_user_id,
                "upstox_user_name": access_token_row.upstox_user_name,
                "upstox_email": access_token_row.upstox_email,
                "access_token": access_token_row.access_token,
                "token_created_at": access_token_row.token_created_at,
                "token_expiry_at": access_token_row.token_expiry_at
            }

        except Exception:

            db.rollback()

            logger.exception(
                "Failed to generate Upstox access token"
            )

            return {
                "success": False,
                "message": "Unable to generate access token"
            }
            
            
#  Request_token
   
    @staticmethod
    def request_token(
        db: Session,
        upstox_user_id: str
    ):

        upstox_user_id = upstox_user_id.strip()
        if not upstox_user_id:
            return {
                "success": False,
                "message": "Upstox User ID is required"
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
                "message": "Access token not found"
            }

        expiry_at = access_token_row.token_expiry_at
        if (
            not expiry_at
            or _now_ist_naive() >= _as_ist_naive(expiry_at)
        ):
            return {
                "success": False,
                "message": "Access token expired. Login again."
            }

        return {
            "success": True,
            "upstox_user_id":
                access_token_row.upstox_user_id,
            "upstox_user_name":
                access_token_row.upstox_user_name,
            "upstox_email":
                access_token_row.upstox_email,
            "access_token":
                access_token_row.access_token,
            "token_created_at":
                access_token_row.token_created_at,
            "token_expiry_at":
                access_token_row.token_expiry_at
        }
        
        
    # Logout

    @staticmethod
    def logout(
        db: Session,
        upstox_user_id: str
    ):
        try:
            # STEP 1: Check karo ki user exist karta hai
            user = (
                db.query(User)
                .filter(User.upstox_user_id == upstox_user_id)
                .first()
            )

            if not user:
                return {
                    "success": False,
                    "local_logout": False,
                    "upstox_logout": False,
                    "message": "Invalid user ID. User not found."
                }

            # STEP 2: Isi user ka access token nikalo
            access_token_row = (
                db.query(AccessToken)
                .filter(AccessToken.upstox_user_id == upstox_user_id)
                .first()
            )

            # Token nhi hai toh logout mat karo
            if (
                not access_token_row
                or not access_token_row.access_token
                or not access_token_row.access_token.strip()
            ):
                return {
                    "success": False,
                    "local_logout": False,
                    "upstox_logout": False,
                    "message": (
                        "No access token found for this user. "
                        "Nothing was changed."
                    )
                }

            access_token = access_token_row.access_token.strip()

            # STEP 3: Pehle Upstox se logout karvao
            try:
                response = requests.delete(
                    settings.UPSTOX_LOGOUT_URL,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}"
                    },
                    timeout=10
                )

                try:
                    data = response.json()
                except ValueError:
                    data = {
                        "message": response.text
                    }

            except requests.RequestException:
                # Network error: local token ko mat delete karo
                return {
                    "success": False,
                    "local_logout": False,
                    "upstox_logout": False,
                    "message": (
                        "Could not contact Upstox. "
                        "Local login remains unchanged."
                    )
                }

            # STEP 4: Upstox ka actual response verify karo
            upstox_logout_success = (
                response.status_code == 200
                and isinstance(data, dict)
                and data.get("status") == "success"
                and data.get("data") is True
            )

            # Upstox logout fail hua toh yahin ruk jao
            if not upstox_logout_success:
                return {
                    "success": False,
                    "local_logout": False,
                    "upstox_logout": False,
                    "message": (
                        "Upstox logout failed. "
                        "Local token was not deleted."
                    ),
                    "response": data
                }

            # STEP 5: Upstox success ke baad local row nikalo
            login_row = (
                db.query(UpstoxUserLogin)
                .filter(
                    UpstoxUserLogin.upstox_user_id == upstox_user_id
                )
                .first()
            )

            # STEP 6: Sirf isi user ka token delete karo
            db.delete(access_token_row)

            # Purana authorization code/state clear karo
            if login_row:
                login_row.code = None
                login_row.state = None

            # STEP 7: Changes database mein save karo
            db.commit()

            return {
                "success": True,
                "local_logout": True,
                "upstox_logout": True,
                "message": "Logout successful"
            }

        except Exception:
            db.rollback()

            return {
                "success": False,
                "local_logout": False,
                "upstox_logout": False,
                "message": (
                    "Logout failed. "
                    "Local database changes were rolled back."
                )
            }
