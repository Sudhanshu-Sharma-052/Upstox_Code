from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

class AccountFundsConfig(BaseSettings):

    UPSTOX_PROFILE_URL: str
    UPSTOX_FUNDS_MARGIN_URL: str
    UPSTOX_KILL_SWITCH_URL: str
    UPSTOX_STATIC_IP_URL: str
    
# Payments 
    
    UPSTOX_PAYINS_URL: str
    UPSTOX_PAYOUT_URL: str
    UPSTOX_PAYOUT_MODES_URL: str
    UPSTOX_PAYOUT_REQUEST_URL: str
    UPSTOX_MODIFY_PAYOUT_URL: str
    
# Charges
    
    UPSTOX_BROKERAGE_URL: str
    
# Margins 
    
    UPSTOX_MARGIN_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

account_funds_settings = (
    AccountFundsConfig()
)