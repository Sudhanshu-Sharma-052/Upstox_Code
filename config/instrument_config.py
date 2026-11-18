from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict
)

class InstrumentSettings(
    BaseSettings
):

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    UPSTOX_INSTRUMENT_URL: str
    UPSTOX_INSTRUMENT_SEARCH_URL: str

instrument_settings = (
    InstrumentSettings()
)