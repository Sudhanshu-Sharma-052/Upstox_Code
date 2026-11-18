from typing import Optional
from pydantic import BaseModel


class PayinsRequest(BaseModel):
    upstox_user_id: str


class PayoutRequest(
    BaseModel
):

    mode: str

    amount: float
    
    
class ModifyPayoutRequest(
    BaseModel
):

    amount: float    


class CancelPayoutRequest(BaseModel):

    upstox_user_id: str    
      

class BrokerageRequest(
    BaseModel
):

    upstox_user_id: str

    instrument_token: str

    quantity: int

    product: str

    transaction_type: str

    price: float
    

class MarginInstrument(
    BaseModel
):

    instrument_key: str

    quantity: int

    transaction_type: str

    product: str

    price: Optional[float] = None


class MarginRequest(
    BaseModel
):

    upstox_user_id: str

    instruments: list[MarginInstrument]  
