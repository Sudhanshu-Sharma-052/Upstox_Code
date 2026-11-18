from typing import Literal

from pydantic import BaseModel, Field


class MarketDataSubscriptionData(BaseModel):
    mode: Literal[
        "ltpc",
        "option_greeks",
        "full",
        "full_d30"
    ] = "ltpc"

    instrumentKeys: list[str] = Field(min_length=1)


class MarketDataSubscriptionRequest(BaseModel):
    guid: str
    method: Literal[
        "sub",
        "change_mode",
        "unsub"
    ] = "sub"

    data: MarketDataSubscriptionData
    
    
    


class PortfolioStreamRequest(BaseModel):

    update_types: list[
        Literal[
            "order",
            "gtt_order",
            "position",
            "holding",
        ]
    ] = Field(
        default_factory=lambda: ["order"],
        min_length=1,
        description="Portfolio update types",
    )

