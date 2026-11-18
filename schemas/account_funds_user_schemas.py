from typing import Optional
from typing import List
from pydantic import BaseModel


class ProfileResponse(
    BaseModel
):

    status: str
    data: dict


class AccountFundsUserRequest(
    BaseModel
):

    upstox_user_id: str
    segment: Optional[str] = None


class KillSwitchItem(
    BaseModel
):

    segment: str
    action: str


class KillSwitchRequest(
    BaseModel
):

    upstox_user_id: str
    updates: List[
        KillSwitchItem
    ]
    
    
class KillSwitchStatusRequest(
    BaseModel
):

    upstox_user_id: str    
    
    
class StaticIPRequest(
    BaseModel
):

    upstox_user_id: str 
    
    
class UpdateStaticIPRequest(
    BaseModel
):

    upstox_user_id: str

    primary_ip: str

    secondary_ip: Optional[str] = None       