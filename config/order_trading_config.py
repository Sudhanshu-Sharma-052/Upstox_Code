from pydantic_settings import BaseSettings, SettingsConfigDict

class OrderTradingSettings(BaseSettings):

    UPSTOX_PLACE_ORDER_URL: str
    UPSTOX_MULTI_ORDER_URL: str
    UPSTOX_MODIFY_ORDER_URL: str
    UPSTOX_CANCEL_ORDER_URL: str
    UPSTOX_CANCEL_MULTI_ORDER_URL: str
    UPSTOX_EXIT_ALL_POSITIONS_URL: str
    UPSTOX_ORDER_DETAILS_URL: str
    UPSTOX_ORDER_HISTORY_URL: str
    UPSTOX_ORDER_BOOK_URL: str
    UPSTOX_GET_TRADES_URL: str 
    UPSTOX_GET_TRADES_URL: str 
    UPSTOX_HISTORICAL_TRADES_URL: str

    
    
    # GTT ORDER 
    
    UPSTOX_GTT_PLACE_URL: str
    UPSTOX_GTT_MODIFY_URL: str
    UPSTOX_GTT_CANCEL_URL: str
    UPSTOX_GTT_DETAILS_URL: str
    
    
#  IPO 

    UPSTOX_IPO_LIST_URL: str   

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

order_trading_settings = OrderTradingSettings()