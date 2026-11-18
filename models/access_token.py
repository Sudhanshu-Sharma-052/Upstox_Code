from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from datetime import datetime
from database.base import Base


class AccessToken(Base):

    __tablename__ = "access_token"

    id = Column(Integer, primary_key=True, index=True)

    upstox_user_id = Column(
        String(255),
        nullable=False,
        index=True
    )

    upstox_user_name = Column(String(255), nullable=True)

    upstox_email = Column(String(255), nullable=True)

    access_token = Column(String(5000), nullable=False)

    token_created_at = Column(DateTime, nullable=True)

    token_expiry_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )