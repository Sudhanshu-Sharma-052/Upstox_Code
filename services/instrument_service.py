import gzip
import json
import requests

from datetime import datetime

from sqlalchemy.orm import Session

from sqlalchemy import and_, func, or_

from models.instrument import Instrument

from config.instrument_config import (
    instrument_settings
)
from config.index_data_config import DEFAULT_INDICES


class InstrumentService:

    ALLOWED_INDEX_SYMBOLS = tuple(DEFAULT_INDICES.keys())
    ALLOWED_INDEX_KEYS = tuple(DEFAULT_INDICES.values())

    @classmethod
    def is_allowed_instrument(cls, item):

        if not isinstance(item, dict):
            return False

        if item.get("instrument_key") in cls.ALLOWED_INDEX_KEYS:
            return True

        segment = str(item.get("segment") or "").upper()
        if not segment.endswith("_FO"):
            return False

        underlying_key = item.get("underlying_key")
        underlying_symbol = str(
            item.get("underlying_symbol") or ""
        ).strip().upper()
        name = str(item.get("name") or "").strip().upper()

        return (
            underlying_key in cls.ALLOWED_INDEX_KEYS
            or underlying_symbol in cls.ALLOWED_INDEX_SYMBOLS
            or name in cls.ALLOWED_INDEX_SYMBOLS
        )

# Sync_instruments 

    @staticmethod
    def sync_instruments(
        db: Session
    ):

        response = requests.get(
            instrument_settings.UPSTOX_INSTRUMENT_URL,
            timeout=120
        )

        response.raise_for_status()

        data = json.loads(
            gzip.decompress(
                response.content
            )
        )

        db.query(
            Instrument
        ).delete()

        db.commit()

        instruments = []

        for item in data:

            if not InstrumentService.is_allowed_instrument(item):
                continue

            expiry = None

            expiry_value = item.get(
                "expiry"
            )

            if expiry_value:

                try:

                    if isinstance(
                        expiry_value,
                        int
                    ):

                        expiry = datetime.fromtimestamp(
                            expiry_value / 1000
                        ).date()

                    else:

                        expiry = datetime.strptime(
                            str(expiry_value)[:10],
                            "%Y-%m-%d"
                        ).date()

                except Exception:

                    expiry = None

            strike_price = None

            try:

                strike_price = float(
                    item.get(
                        "strike_price",
                        0
                    )
                )

            except Exception:

                strike_price = None

            instruments.append(

                Instrument(

                    segment=item.get(
                        "segment"
                    ),

                    exchange=item.get(
                        "exchange"
                    ),

                    name=item.get(
                        "name"
                    ),

                    isin=item.get(
                        "isin"
                    ),

                    instrument_type=item.get(
                        "instrument_type"
                    ),

                    instrument_key=item.get(
                        "instrument_key"
                    ),

                    exchange_token=item.get(
                        "exchange_token"
                    ),

                    trading_symbol=item.get(
                        "trading_symbol"
                    ),

                    short_name=item.get(
                        "short_name"
                    ),

                    security_type=item.get(
                        "security_type"
                    ),

                    lot_size=item.get(
                        "lot_size",
                        0
                    ),

                    minimum_lot=item.get(
                        "minimum_lot",
                        0
                    ),

                    freeze_quantity=item.get(
                        "freeze_quantity",
                        0
                    ),

                    tick_size=item.get(
                        "tick_size",
                        0
                    ),

                    expiry=expiry,

                    strike_price=strike_price,

                    weekly=item.get(
                        "weekly",
                        False
                    ),

                    underlying_symbol=item.get(
                        "underlying_symbol"
                    ),

                    underlying_key=item.get(
                        "underlying_key"
                    ),

                    underlying_type=item.get(
                        "underlying_type"
                    )
                )
            )

        batch_size = 5000

        for i in range(
            0,
            len(instruments),
            batch_size
        ):

            db.bulk_save_objects(
                instruments[
                    i:i + batch_size
                ]
            )

            db.commit()

        return {
            "success": True,
            "count": len(instruments),
            "message": "Instrument sync completed"
        }
        
        
# Search_instrument 

    @staticmethod
    def search_instrument(
        db: Session,
        search: str
    ):

        instruments = (

            db.query(
                Instrument
            )

            .filter(

                or_(

                    Instrument.trading_symbol.ilike(
                        f"%{search}%"
                    ),

                    Instrument.name.ilike(
                        f"%{search}%"
                    ),

                    Instrument.instrument_key.ilike(
                        f"%{search}%"
                    ),

                    Instrument.short_name.ilike(
                        f"%{search}%"
                    )
                )
            )

            .filter(
                or_(
                    Instrument.instrument_key.in_(
                        InstrumentService.ALLOWED_INDEX_KEYS
                    ),
                    and_(
                        Instrument.segment.ilike("%_FO"),
                        or_(
                            Instrument.underlying_key.in_(
                                InstrumentService.ALLOWED_INDEX_KEYS
                            ),
                            func.upper(
                                Instrument.underlying_symbol
                            ).in_(
                                InstrumentService.ALLOWED_INDEX_SYMBOLS
                            ),
                            func.upper(
                                Instrument.name
                            ).in_(
                                InstrumentService.ALLOWED_INDEX_SYMBOLS
                            ),
                        ),
                    ),
                )
            )

            .limit(50)

            .all()
        )

        result = []

        for item in instruments:

            result.append({

                "id": item.id,

                "segment": item.segment,

                "exchange": item.exchange,

                "name": item.name,

                "instrument_type": item.instrument_type,

                "instrument_key": item.instrument_key,

                "trading_symbol": item.trading_symbol,

                "short_name": item.short_name,

                "lot_size": item.lot_size,

                "freeze_quantity": item.freeze_quantity,

                "tick_size": item.tick_size,

                "expiry":
                    str(item.expiry)
                    if item.expiry
                    else None,

                "strike_price":
                    item.strike_price
            })

        return {

            "success": True,

            "count":
                len(result),

            "data":
                result
        }     
