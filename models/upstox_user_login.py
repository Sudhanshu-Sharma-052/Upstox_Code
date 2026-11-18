from database.base import Base
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from datetime import datetime
from datetime import timezone
from datetime import timedelta

IST = timezone(
    timedelta(hours=5, minutes=30)
)


class UpstoxUserLogin(Base):

    __tablename__ = "upstox_user_login"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True
    )

    upstox_user_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    state = Column(
        String(255),
        nullable=True
    )

    code = Column(
        String(255),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(IST)
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(IST),
        onupdate=lambda: datetime.now(IST)
    )


class AccessToken(Base):

    __tablename__ = "access_token"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True
    )

    upstox_user_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    upstox_user_name = Column(
        String(255),
        nullable=True
    )

    upstox_email = Column(
        String(255),
        nullable=True
    )

    access_token = Column(
        String(5000),
        nullable=False
    )

    token_created_at = Column(
        DateTime,
        nullable=True
    )

    token_expiry_at = Column(
        DateTime,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(IST)
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(IST),
        onupdate=lambda: datetime.now(IST)
    )
