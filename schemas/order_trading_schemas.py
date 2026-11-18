from typing import Literal
from pydantic import BaseModel, Field, model_validator


class PlaceOrderRequest(BaseModel):
    quantity: int = Field(
        gt=0,
        description="Quantity of the instrument to be ordered.",
    )

    product: Literal["I", "D", "MTF"]

    validity: Literal["DAY", "IOC"] = "DAY"

    price: float = Field(ge=0)

    tag: str | None = Field(default=None, max_length=20)

    instrument_token: str = Field(min_length=1)

    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]

    transaction_type: Literal["BUY", "SELL"]

    disclosed_quantity: int = Field(default=0, ge=0)

    trigger_price: float = Field(default=0, ge=0)

    is_amo: bool = False

    slice: bool = False

    market_protection: int = -1

    @model_validator(mode="after")
    def validate_order_prices(self):
        if self.order_type == "LIMIT" and self.price <= 0:
            raise ValueError(
                "Price must be greater than zero for LIMIT orders."
            )

        if self.order_type == "SL":
            if self.price <= 0 or self.trigger_price <= 0:
                raise ValueError(
                    "Price and trigger_price must be greater than zero "
                    "for SL orders."
                )

        if self.order_type == "SL-M" and self.trigger_price <= 0:
            raise ValueError(
                "trigger_price must be greater than zero for SL-M orders."
            )

        if self.market_protection != -1 and not (
            0 <= self.market_protection <= 25
        ):
            raise ValueError(
                "market_protection must be -1 or a value between 0 and 25."
            )

        return self
    
        
class MultiOrderItem(BaseModel):
    correlation_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    product: str
    validity: str = "DAY"
    price: float = Field(ge=0)
    tag: str | None = Field(default=None, max_length=40)
    instrument_token: str
    order_type: str
    transaction_type: str
    disclosed_quantity: int = Field(default=0, ge=0)
    trigger_price: float = Field(default=0, ge=0)
    is_amo: bool = False
    slice: bool = False
    market_protection: int = -1


class MultiOrderRequest(BaseModel):
    orders: list[MultiOrderItem] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_correlation_ids(self):
        correlation_ids = [
            order.correlation_id for order in self.orders
        ]

        if len(correlation_ids) != len(set(correlation_ids)):
            raise ValueError(
                "Duplicate correlation_id found. "
                "Every order must have a unique correlation_id."
            )

        return self
    
       
class ModifyOrderRequest(BaseModel):
    order_id: str
    validity: Literal["DAY", "IOC"]
    price: float = Field(ge=0)
    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]
    trigger_price: float = Field(ge=0)

    quantity: int | None = Field(default=None, gt=0)
    disclosed_quantity: int | None = Field(default=None, ge=0)
    market_protection: int | None = Field(default=None, ge=-1, le=25)