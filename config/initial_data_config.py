from pydantic_settings import BaseSettings, SettingsConfigDict


class InitialDataSettings(BaseSettings):

    UPSTOX_INITIAL_DATA_POSITIONS_URL: str
    UPSTOX_INITIAL_DATA_LTP_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


initial_data_settings = InitialDataSettings()
