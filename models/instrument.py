from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    Boolean,
    BigInteger
)
from database.database import Base


class Instrument(Base):

    __tablename__ = "instrument"

    id = Column(Integer, primary_key=True, autoincrement=True)

    segment = Column(String(100))
    exchange = Column(String(50))

    name = Column(String(255))
    isin = Column(String(100))

    instrument_type = Column(String(50))

    instrument_key = Column(
        String(255),
        unique=True,
        index=True
    )

    exchange_token = Column(String(100))

    trading_symbol = Column(
        String(255),
        index=True
    )

    short_name = Column(String(255))
    security_type = Column(String(100))

    lot_size = Column(BigInteger)
    minimum_lot = Column(BigInteger)

    freeze_quantity = Column(Float)

    tick_size = Column(Float)

    expiry = Column(Date)

    strike_price = Column(Float)

    weekly = Column(Boolean)

    underlying_symbol = Column(
        String(255)
    )

    underlying_key = Column(
        String(255)
    )

    underlying_type = Column(
        String(100)
    )