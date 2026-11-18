from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from database.base import Base

IST = ZoneInfo("Asia/Kolkata")

def current_ist_time():
    return datetime.now(IST).replace(tzinfo=None)


class OrderTrading(Base):

    __tablename__ = "order_trading"

    id = Column(Integer, primary_key=True, index=True)

    upstox_user_id = Column(String(255), nullable=False, index=True)

    upstox_order_id = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    instrument_token = Column(String(100), nullable=False)

    quantity = Column(Integer, nullable=False)

    product = Column(String(10), nullable=False)

    validity = Column(String(10), nullable=False)

    price = Column(Float, nullable=False, default=0)

    order_type = Column(String(20), nullable=False)

    transaction_type = Column(String(10), nullable=False)

    tag = Column(String(20), nullable=True)

    disclosed_quantity = Column(Integer, nullable=False, default=0)

    trigger_price = Column(Float, nullable=False, default=0)

    is_amo = Column(Boolean, nullable=False, default=False)

    slice = Column(Boolean, nullable=False, default=False)

    market_protection = Column(Integer, nullable=False, default=-1)

    status = Column(String(30), nullable=False, default="PLACED")

    upstox_response = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=current_ist_time,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=current_ist_time,
        onupdate=current_ist_time,
    )
