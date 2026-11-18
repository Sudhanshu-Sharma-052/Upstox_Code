from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
)
from database.base import Base


class GTTOrder(Base):
    __tablename__ = "gtt_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    upstox_user_id = Column(String(255), nullable=False, index=True)

    gtt_order_id = Column(String(100), nullable=True, index=True)

    instrument_token = Column(String(100), nullable=False)
    transaction_type = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    product = Column(String(10), nullable=False)

    request_payload = Column(JSON, nullable=False)
    upstox_response = Column(JSON, nullable=True)

    status = Column(String(30), nullable=False, default="PENDING")

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
