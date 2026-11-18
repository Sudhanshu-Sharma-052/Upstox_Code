from pydantic_settings import BaseSettings, SettingsConfigDict


class WebsocketMarketDataSettings(BaseSettings):

    UPSTOX_MARKET_DATA_AUTHORIZE_URL: str
    UPSTOX_PORTFOLIO_STREAM_AUTHORIZE_URL: str
    
    UPSTOX_PORTFOLIO_STREAM_URL: str
    UPSTOX_PORTFOLIO_STREAM_AUTHORIZE_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


websocket_market_data_settings = WebsocketMarketDataSettings()