import re
from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):

    upstox_user_id: str = Field(
        min_length=1,
        max_length=255
    )

    first_name: str = Field(
        min_length=1,
        max_length=100
    )

    last_name: str = Field(
        min_length=1,
        max_length=100
    )

    email: EmailStr

    upstox_client_id: str = Field(
        min_length=1,
        max_length=255
    )

    upstox_client_secret: str = Field(
        min_length=1,
        max_length=500
    )

    password: str = Field(
        min_length=1,
        max_length=255
    )

    @field_validator(
        "upstox_user_id",
        "first_name",
        "last_name",
        "upstox_client_id",
        "upstox_client_secret",
        "password"
    )
    @classmethod
    def validate_not_empty(cls, value: str) -> str:

        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty")

        return value

    @field_validator("upstox_client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:

        value = value.strip()

        # Reject Swagger placeholders
        if value.lower() in {
            "string",
            "your_upstox_client_id",
            "your_client_id",
            "test"
        }:
            raise ValueError(
                "Enter the actual Upstox API key, not a placeholder"
            )

        # Validate UUID-style client ID format
        pattern = (
            r"^[0-9a-fA-F]{8}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{12}$"
        )

        if not re.fullmatch(pattern, value):
            raise ValueError(
                "Invalid client_id format. Enter the API key from your Upstox Developer App"
            )

        return value

    @field_validator("upstox_client_secret")
    @classmethod
    def validate_client_secret(cls, value: str) -> str:

        value = value.strip()

        # Reject Swagger placeholders
        if value.lower() in {
            "string",
            "your_upstox_client_secret",
            "your_client_secret",
            "test"
        }:
            raise ValueError(
                "Enter the actual Upstox API secret, not a placeholder"
            )

        if len(value) < 8:
            raise ValueError(
                "Client secret is too short"
            )

        return value


class UserCredentialsCreate(BaseModel):

    upstox_user_id: str = Field(
        min_length=1,
        max_length=255
    )

    upstox_client_id: str = Field(
        min_length=1,
        max_length=255
    )

    upstox_client_secret: str = Field(
        min_length=1,
        max_length=500
    )

    @field_validator("upstox_user_id")
    @classmethod
    def validate_upstox_user_id(cls, value: str) -> str:

        value = value.strip()

        if not value:
            raise ValueError("Upstox User ID cannot be empty")

        return value

    @field_validator("upstox_client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:

        value = value.strip()

        if value.lower() in {
            "string",
            "your_upstox_client_id",
            "your_client_id",
            "test"
        }:
            raise ValueError(
                "Enter the actual Upstox API key, not a placeholder"
            )

        pattern = (
            r"^[0-9a-fA-F]{8}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{12}$"
        )

        if not re.fullmatch(pattern, value):
            raise ValueError(
                "Invalid client_id format. Enter the API key from your Upstox Developer App"
            )

        return value

    @field_validator("upstox_client_secret")
    @classmethod
    def validate_client_secret(cls, value: str) -> str:

        value = value.strip()

        if value.lower() in {
            "string",
            "your_upstox_client_secret",
            "your_client_secret",
            "test"
        }:
            raise ValueError(
                "Enter the actual Upstox API secret, not a placeholder"
            )

        if len(value) < 8:
            raise ValueError(
                "Client secret is too short"
            )

        return value


class UserCredentialsResponse(BaseModel):

    success: bool
    message: str


class UpstoxLoginRequest(BaseModel):

    upstox_user_id: str = Field(
        min_length=1,
        max_length=255
    )

    password: str = Field(
        min_length=1,
        max_length=255
    )

    @field_validator(
        "upstox_user_id",
        "password"
    )
    @classmethod
    def validate_not_empty(cls, value: str) -> str:

        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty")

        return value


class ForgotPasswordRequest(BaseModel):

    upstox_user_id: str = Field(
        min_length=1,
        max_length=255
    )

    email: EmailStr

    new_password: str = Field(
        min_length=1,
        max_length=255
    )

    @field_validator("upstox_user_id", "new_password")
    @classmethod
    def validate_not_empty(cls, value: str) -> str:

        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty")

        return value
