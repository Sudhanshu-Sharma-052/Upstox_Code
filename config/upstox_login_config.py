from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

class Settings(BaseSettings):

    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str

    # UPSTOX_CLIENT_ID: str
    # UPSTOX_CLIENT_SECRET: str
    
    UPSTOX_REDIRECT_URI: str
    UPSTOX_AUTHORIZE_URL: str
    UPSTOX_TOKEN_URL: str
    UPSTOX_REQUEST_TOKEN_URL: str
    UPSTOX_LOGOUT_URL: str
    
    # UPSTOX_PROFILE_URL: str
    # UPSTOX_FUNDS_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @property
    def DATABASE_URL(self) -> str:

        return (
            f"mysql+pymysql://"
            f"{self.MYSQL_USER}:"
            f"{self.MYSQL_PASSWORD}@"
            f"{self.MYSQL_HOST}:"
            f"{self.MYSQL_PORT}/"
            f"{self.MYSQL_DB}"
        )

settings = Settings()