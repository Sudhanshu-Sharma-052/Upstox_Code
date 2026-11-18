import json
import logging

from datetime import date
from pathlib import Path
from decimal import Decimal

import requests

from sqlalchemy.orm import Session
from sqlalchemy import cast, Float, func

from fastapi import HTTPException

from models.signup_user import User
from models.upstox_user_login import AccessToken
from models.instrument import Instrument

from services.order_trading_service import OrderTradingService
from services.account_funds_user_service import AccountFundsUserService
from config.index_data_config import DEFAULT_INDICES
from config.initial_data_config import initial_data_settings


logger = logging.getLogger(__name__)


class InitialDataService:

    OPTION_SYMBOLS = (
        "NIFTY",
        "BANKEX",
        "BANKNIFTY",
        "FINNIFTY",
        "MIDCPNIFTY",
        "SENSEX",
    )

    def __init__(self, db: Session):
        self.db = db

    async def get_initial_data(self, upstox_user_id: str):

        # Check user
        user = (
            self.db.query(User)
            .filter(User.upstox_user_id == upstox_user_id)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found."
            )

        # Get user's Upstox access token
        token = (
            self.db.query(AccessToken)
            .filter(
                AccessToken.upstox_user_id == upstox_user_id
            )
            .order_by(AccessToken.id.desc())
            .first()
        )

        if not token or not token.access_token:
            raise HTTPException(
                status_code=401,
                detail="Please login to Upstox first."
            )

        # Load original frontend JSON
        payload = self.load_initial_data_template()

        index_instruments = self.get_index_instruments()
        index_prices = self.get_market_prices(
            index_instruments,
            token.access_token,
        )

        # Get expiry dates
        expiry_map = self.get_latest_expiries(
            payload.get("expiry", {})
        )

        # Get instruments
        instruments = self.get_instruments(
            expiry_map,
            payload,
            index_prices,
        )

        option_prices = self.get_market_prices(
            [
                instrument
                for instrument in instruments
                if instrument.get("instrument_type") in ("CE", "PE")
            ],
            token.access_token,
        )
        for instrument in instruments:
            if instrument.get("instrument_type") in ("CE", "PE"):
                instrument["last_price"] = option_prices.get(
                    instrument.get("instrument_token"),
                    0,
                )

        # Get orders
        fno_instrument_keys = self.get_fno_instrument_keys()
        orders = await self.get_orders(
            upstox_user_id,
            fno_instrument_keys,
        )

        # Get positions
        positions = self.get_positions(
            token.access_token,
            fno_instrument_keys,
        )

        # Get margins
        margins = self.get_margins(
            upstox_user_id
        )

        # Update original frontend response
        payload["expiry"] = expiry_map
        payload["instruments"] = instruments
        payload["orders"] = orders
        payload["positions"] = positions
        payload["margins"] = margins

        # Apply user details
        self.apply_user_defaults(
            payload,
            upstox_user_id
        )

        # Update dates
        self.apply_dynamic_dates(payload)

        # Update freeze limits
        self.apply_freeze_limits(
            payload,
            upstox_user_id,
            expiry_map,
        )

        # Update capital entity
        self.apply_capital_entity(
            payload,
            upstox_user_id,
            margins
        )

        return self.sanitize_for_json(payload)

    # --------------------------------------------------
    # LOAD INITIAL DATA JSON TEMPLATE
    # --------------------------------------------------

    def load_initial_data_template(self):

        file_path = self.initial_data_file_path()

        if not file_path.is_file():

            logger.error(
                "Initial data template not found: %s",
                file_path
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Initial data template file not found. "
                    f"Expected path: {file_path}"
                )
            )

        try:

            if file_path.stat().st_size == 0:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        "Initial data template is empty. "
                        "Add the complete frontend JSON to "
                        "data/initial_data.json."
                    )
                )

            with file_path.open(
                "r",
                encoding="utf-8-sig"
            ) as file:

                payload = json.load(file)

        except json.JSONDecodeError as exc:

            logger.exception(
                "Invalid JSON in initial data template: %s",
                file_path
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Invalid JSON in data/initial_data.json. "
                    f"Line {exc.lineno}, "
                    f"column {exc.colno}: {exc.msg}"
                )
            ) from exc

        except OSError as exc:

            logger.exception(
                "Unable to read initial data template: %s",
                file_path
            )

            raise HTTPException(
                status_code=500,
                detail="Unable to read initial data template file."
            ) from exc

        if not isinstance(payload, dict):

            raise HTTPException(
                status_code=500,
                detail=(
                    "Initial data template must contain "
                    "a JSON object at the root."
                )
            )

        required_keys = (
            "expiry",
            "quantity",
            "orders",
            "positions",
            "margins",
            "instruments",
            "systemPositions",
            "user_id",
            "user_Type",
            "user_isForAll",
            "user_isMultiUser",
            "slBackendValues",
            "capitalEntity",
            "authId",
            "authIdDTO",
            "sellingEntity",
            "splitPositions",
            "multiUserPositions",
            "multiUserOrders",
            "constantMongEntity",
            "freezeLimitEntity",
        )

        missing_keys = [
            key
            for key in required_keys
            if key not in payload
        ]

        if missing_keys:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Initial data template is missing "
                    "required frontend keys: "
                    + ", ".join(missing_keys)
                )
            )

        return payload

    def initial_data_file_path(self):

        return (
            Path(__file__).resolve().parents[1]
            / "data"
            / "initial_data.json"
        )

    # --------------------------------------------------
    # GET LATEST EXPIRY DATES
    # --------------------------------------------------

    def get_latest_expiries(self, template_expiry):

        today = date.today()
        expiry_map = {}

        for symbol in self.OPTION_SYMBOLS:
            expiry_limit = max(
                len(template_expiry.get(symbol) or []),
                1,
            )

            expiries = (
                self.db.query(Instrument.expiry)
                .filter(
                    Instrument.name == symbol,
                    Instrument.expiry >= today,
                    Instrument.instrument_type.in_(
                        ("CE", "PE")
                    )
                )
                .distinct()
                .order_by(Instrument.expiry)
                .limit(expiry_limit)
                .all()
            )

            expiry_map[symbol] = [
                str(row[0])
                for row in expiries
            ]

        return expiry_map

    # --------------------------------------------------
    # GET OPTION INSTRUMENTS
    # --------------------------------------------------

    def get_index_instruments(self):

        index_keys = list(DEFAULT_INDICES.values())
        rows = (
            self.db.query(Instrument)
            .filter(
                Instrument.instrument_key.in_(index_keys),
                Instrument.instrument_type == "INDEX",
            )
            .all()
        )
        rows_by_key = {
            row.instrument_key: row
            for row in rows
        }

        return [
            rows_by_key[key]
            for key in index_keys
            if key in rows_by_key
        ]

    def get_market_prices(self, instruments, access_token):

        instrument_keys = [
            instrument.instrument_key
            if isinstance(instrument, Instrument)
            else instrument.get("instrument_token")
            for instrument in instruments
        ]
        instrument_keys = [
            key
            for key in instrument_keys
            if key
        ]

        if not instrument_keys:
            return {}

        try:
            response = requests.get(
                initial_data_settings.UPSTOX_INITIAL_DATA_LTP_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                params={
                    "instrument_key": ",".join(instrument_keys),
                },
                timeout=15,
            )
            response.raise_for_status()
            response_data = response.json()
            quote_data = response_data.get("data", {})

            if not isinstance(quote_data, dict):
                return {}

            prices = {}
            for quote in quote_data.values():
                if not isinstance(quote, dict):
                    continue

                instrument_key = quote.get("instrument_token")
                last_price = self.to_float(
                    quote.get("last_price")
                )
                if instrument_key and last_price is not None:
                    prices[instrument_key] = last_price

            return prices

        except Exception:
            logger.exception(
                "Initial data Upstox LTP fetch failed."
            )
            return {}

    def get_instruments(self, expiry_map, payload, index_prices):

        scope = self.get_template_instrument_scope(payload)
        symbol = scope["symbol"]
        expiries = expiry_map.get(symbol) or []

        if not expiries:
            return scope["placeholders"]

        target_expiry = date.fromisoformat(expiries[0])
        anchor_strike = index_prices.get(
            DEFAULT_INDICES.get(symbol)
        ) or scope["anchor_strike"]
        instruments = []

        for option_type in ("CE", "PE"):
            query = self.db.query(Instrument).filter(
                Instrument.name == symbol,
                Instrument.expiry == target_expiry,
                Instrument.instrument_type == option_type,
            )

            strike_order = cast(Instrument.strike_price, Float)

            if anchor_strike is not None:
                query = query.order_by(
                    func.abs(strike_order - anchor_strike),
                    strike_order,
                )
            else:
                query = query.order_by(strike_order)

            limit = max(
                scope["type_limits"].get(option_type, 0),
                1,
            )
            instruments.extend(query.limit(limit).all())

        instruments.sort(
            key=lambda inst: (
                float(inst.strike_price or 0),
                inst.instrument_type or "",
            )
        )

        option_rows = [
            self.serialize_instrument(inst)
            for inst in instruments
        ]

        return option_rows + scope["placeholders"]

    def get_template_instrument_scope(self, payload):

        template_instruments = payload.get("instruments", [])
        option_rows = [
            row
            for row in template_instruments
            if isinstance(row, dict)
            and row.get("name")
            and row.get("instrumentType") in ("CE", "PE")
        ]
        placeholders = [
            row
            for row in template_instruments
            if isinstance(row, dict)
            and not row.get("name")
        ]

        type_limits = {
            "CE": sum(
                row.get("instrumentType") == "CE"
                for row in option_rows
            ),
            "PE": sum(
                row.get("instrumentType") == "PE"
                for row in option_rows
            ),
        }
        symbol = option_rows[0].get("name") if option_rows else "NIFTY"
        strike_fields = {
            "NIFTY": "otmNiftyStrikeCE",
            "BANKNIFTY": "otmBankNiftyStrikeCE",
            "FINNIFTY": "otmFinNiftyStrikeCE",
            "MIDCPNIFTY": "otmMidCpNiftyStrikeCE",
            "SENSEX": "otmSensexStrikeCE",
            "BANKEX": "otmBankexStrikeCE",
        }
        selling_entity = payload.get("sellingEntity") or {}

        return {
            "symbol": symbol,
            "type_limits": type_limits,
            "placeholders": placeholders,
            "anchor_strike": self.to_float(
                selling_entity.get(strike_fields.get(symbol))
            ),
        }

    # --------------------------------------------------
    # SERIALIZE INSTRUMENT
    # --------------------------------------------------

    def serialize_instrument(self, inst, last_price=0):

        return {
            "instrument_token": inst.instrument_key,
            "exchange_token": inst.exchange_token,
            "tradingsymbol": inst.trading_symbol,
            "name": inst.name,
            "last_price": last_price,
            "tick_size": inst.tick_size or 0,
            "instrumentType": inst.instrument_type,
            "segment": inst.segment,
            "exchange": inst.exchange,
            "strike": (
                str(inst.strike_price)
                if inst.strike_price is not None
                else None
            ),
            "lot_size": inst.lot_size or 0,
            "expiry": (
                str(inst.expiry)
                if inst.expiry
                else None
            ),
            "freeze_limit": inst.freeze_quantity or 0,
            "platform": "upstox",
            "position": False,
            "conditional": False,
            "instrument_type": inst.instrument_type,
        }

    # --------------------------------------------------
    # GET ORDERS
    # --------------------------------------------------

    def get_fno_instrument_keys(self):

        rows = (
            self.db.query(Instrument.instrument_key)
            .filter(Instrument.segment.ilike("%_FO"))
            .all()
        )

        return {
            row[0]
            for row in rows
            if row[0]
        }

    async def get_orders(self, upstox_user_id, fno_instrument_keys):

        try:

            response = await OrderTradingService.get_order_book(
                upstox_user_id=upstox_user_id,
                db=self.db
            )

            if (
                isinstance(response, dict)
                and response.get("upstox_success")
            ):

                orders = response.get(
                    "upstox_response",
                    []
                )

                if not isinstance(orders, list):
                    return []

                return [
                    order
                    for order in orders
                    if isinstance(order, dict)
                    and order.get("instrument_token") in fno_instrument_keys
                ]

            logger.warning(
                "Unable to fetch Upstox orders for %s",
                upstox_user_id
            )

            return []

        except Exception:

            logger.exception(
                "Initial data order fetch failed."
            )

            return []

    # --------------------------------------------------
    # GET POSITIONS
    # --------------------------------------------------

    def get_positions(self, access_token, fno_instrument_keys):

        try:

            response = requests.get(
                initial_data_settings.UPSTOX_INITIAL_DATA_POSITIONS_URL,
                headers={
                    "Accept": "application/json",
                    "Api-Version": "2.0",
                    "Authorization": f"Bearer {access_token}"
                },
                timeout=30
            )

            response.raise_for_status()

            response_data = response.json()

            positions = response_data.get("data", [])

            if not isinstance(positions, list):
                return []

            return [
                position
                for position in positions
                if isinstance(position, dict)
                and position.get("instrument_token") in fno_instrument_keys
            ]

        except Exception:

            logger.exception(
                "Initial data positions fetch failed."
            )

            return []

    # --------------------------------------------------
    # GET FUNDS AND MARGIN
    # --------------------------------------------------

    def get_margins(self, upstox_user_id):

        default_margin = {
            "available": {
                "cash": "0",
                "intradayPayin": "0",
                "adhocMargin": "0",
                "collateral": "0",
                "liveBalance": "0"
            },
            "utilised": {
                "m2mUnrealised": "0",
                "m2mRealised": "0",
                "debits": "0",
                "span": "0",
                "optionPremium": "0",
                "holdingSales": "0",
                "exposure": "0",
                "turnover": "0"
            },
            "net": "0"
        }

        try:

            result = (
                AccountFundsUserService.get_funds_and_margin(
                    db=self.db,
                    upstox_user_id=upstox_user_id
                )
            )

            if not result.get("success"):
                return default_margin

            response_data = result.get(
                "response",
                {}
            )

            if not isinstance(response_data, dict):
                return default_margin

            data = response_data.get(
                "data",
                {}
            )

            if not isinstance(data, dict):
                return default_margin

            fno = data.get("fno", {}) or {}
            equity = data.get("equity", {}) or {}

            if (
                not isinstance(fno, dict)
                or not isinstance(equity, dict)
            ):
                return default_margin

            cash = self.to_float(
                fno.get("available_margin")
            )
            if cash is None:
                cash = self.to_float(
                    equity.get("available_margin")
                ) or 0

            span = (
                self.to_float(
                    fno.get("used_margin")
                )
                or 0
            )

            return {
                "available": {
                    "cash": self.format_number(
                        cash
                    ),
                    "intradayPayin": "0",
                    "adhocMargin": "0",
                    "collateral": self.format_number(
                        equity.get("collateral", 0)
                    ),
                    "liveBalance": self.format_number(cash)
                },
                "utilised": {
                    "m2mUnrealised": "0",
                    "m2mRealised": "0",
                    "debits": "0",
                    "span": self.format_number(span),
                    "optionPremium": "0",
                    "holdingSales": "0",
                    "exposure": "0",
                    "turnover": "0"
                },
                "net": self.format_number(cash)
            }

        except Exception:

            logger.exception(
                "Initial data margin fetch failed."
            )

            return default_margin

    # --------------------------------------------------
    # APPLY USER DEFAULTS
    # --------------------------------------------------

    def apply_user_defaults(
        self,
        payload,
        upstox_user_id
    ):

        payload["user_id"] = upstox_user_id

        payload["authId"] = [
            upstox_user_id
        ]

        payload["authIdDTO"] = [
            {
                "userId": upstox_user_id,
                "singleUser": False
            }
        ]

        for key in (
            "capitalEntity",
            "sellingEntity",
            "freezeLimitEntity"
        ):

            if isinstance(payload.get(key), dict):

                payload[key]["userId"] = upstox_user_id

    # --------------------------------------------------
    # APPLY DYNAMIC DATES
    # --------------------------------------------------

    def apply_dynamic_dates(self, payload):

        today = date.today().isoformat()

        date_fields = {
            "capitalEntity": "date",
            "sellingEntity": "latestDate",
            "constantMongEntity": "date",
            "freezeLimitEntity": "update_at"
        }

        for entity, field in date_fields.items():

            value = payload.get(entity)

            if isinstance(value, dict):
                value[field] = today

    # --------------------------------------------------
    # APPLY FREEZE LIMITS
    # --------------------------------------------------

    def apply_freeze_limits(
        self,
        payload,
        upstox_user_id,
        expiry_map,
    ):
        freeze_entity = payload.setdefault(
            "freezeLimitEntity",
            {}
        )

        freeze_entity["userId"] = upstox_user_id

        mappings = {
            "NIFTY": "niftyFreezeQuantities",
            "BANKNIFTY": "bankNiftyFreezeQuantities",
            "FINNIFTY": "finniftyFreezeQuantities",
            "MIDCPNIFTY": "midcapNiftyFreezeQuantities",
            "SENSEX": "sensexFreezeQuantities",
            "BANKEX": "bankexFreezeQuantities"
        }

        for symbol, field in mappings.items():
            expiries = expiry_map.get(symbol) or []
            if not expiries:
                freeze_entity[field] = 0
                continue

            target_expiry = date.fromisoformat(expiries[0])
            freeze_limit = (
                self.db.query(func.min(Instrument.freeze_quantity))
                .filter(
                    Instrument.name == symbol,
                    Instrument.expiry == target_expiry,
                    Instrument.instrument_type.in_(("CE", "PE")),
                    Instrument.freeze_quantity.isnot(None),
                )
                .scalar()
            )
            freeze_entity[field] = self.to_int(freeze_limit) or 0

    # --------------------------------------------------
    # APPLY CAPITAL ENTITY
    # --------------------------------------------------

    def apply_capital_entity(
        self,
        payload,
        upstox_user_id,
        margins
    ):

        capital_entity = payload.get(
            "capitalEntity"
        )

        if not isinstance(capital_entity, dict):
            return

        live_balance = (
            self.to_float(
                margins.get(
                    "available",
                    {}
                ).get("liveBalance")
            )
            or 0
        )

        max_percent = (
            self.to_float(
                capital_entity.get(
                    "maxCapitalUsePercent"
                )
            )
            or 0
        )

        capital_entity["userId"] = upstox_user_id

        capital_entity["startingCapital"] = live_balance

        capital_entity["currentMaxLoss"] = live_balance

        capital_entity["usableBalance"] = live_balance

        capital_entity["totalEquity"] = live_balance

        capital_entity["maxCapitalUse"] = round(
            live_balance * max_percent / 100,
            2
        )

    # --------------------------------------------------
    # HELPER FUNCTIONS
    # --------------------------------------------------

    def format_number(self, value):

        number = self.to_float(value)

        if number is None:
            return "0"

        return str(number)

    def to_int(self, value):

        if value is None or value == "":
            return None

        try:

            return int(
                float(
                    str(value).strip()
                )
            )

        except (TypeError, ValueError):

            return None

    def to_float(self, value):

        if value is None or value == "":
            return None

        try:

            return float(
                str(value).strip()
            )

        except (TypeError, ValueError):

            return None

    # --------------------------------------------------
    # SANITIZE JSON RESPONSE
    # --------------------------------------------------

    def sanitize_for_json(self, value):

        if isinstance(value, dict):

            return {
                key: self.sanitize_for_json(item)
                for key, item in value.items()
            }

        if isinstance(value, list):

            return [
                self.sanitize_for_json(item)
                for item in value
            ]

        if isinstance(value, (date, Decimal)):
            return str(value)

        return value
