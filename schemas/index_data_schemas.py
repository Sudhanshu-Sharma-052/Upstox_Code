
from typing import Literal

from pydantic import BaseModel, Field


class IndexSubscriptionSettings(BaseModel):

    indices: list[str] = Field(
        default_factory=lambda: [
            "BANKEX",
            "SENSEX",
            "NIFTY",
            "FINNIFTY",
            "MIDCAPNIFTY",
            "BANKNIFTY"
        ]
    )

    mode: Literal["ltpc"] = "ltpc"

    strikes_each_side: int = Field(
        default=5,
        ge=0,
        le=20
    )
