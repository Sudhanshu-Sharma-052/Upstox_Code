from sqlalchemy import Boolean, Column, Integer, String, Text

from database.base import Base


class BackendDefaults:

    DEFAULT_CONFIG = {
        "bank_quantity": "30,600",
        "bank_quantity_otm": "30",
        "bank_quantity_atm": "60",
        "bank_quantity_itm": "90",
        "nifty_quantity": "65,1755",
        "nifty_quantity_otm": "65,130",
        "nifty_quantity_atm": "65,130",
        "nifty_quantity_itm": "130,195",
        "fin_quantity": "60,1200",
        "fin_quantity_otm": "60",
        "fin_quantity_atm": "60",
        "fin_quantity_itm": "60",
        "sensex_quantity": "20,1000",
        "sensex_quantity_otm": "20",
        "sensex_quantity_atm": "20",
        "sensex_quantity_itm": "20",
        "bankex_quantity": "30,900",
        "bankex_quantity_otm": "30",
        "bankex_quantity_atm": "4500",
        "bankex_quantity_itm": "2700",
        "mid_cp_nifty_quantity": "120,2760",
        "mid_cp_nifty_quantity_otm": "27600",
        "mid_cp_nifty_quantity_atm": "2760",
        "mid_cp_nifty_quantity_itm": "2760",
        "hotkey_value": "3-5,5-7",
        "hotkey_value_otm": "10-5,12-6,15-8",
        "hotkey_value_atm": "10-5,12-6,15-8",
        "hotkey_value_itm": "10-5,12-6,15-8",
        "bankStrikeCheck": False,
        "niftyStrikeCheck": False,
        "finStrikeCheck": False,
        "bank_strikes": None,
        "nifty_strikes": None,
        "fin_strikes": None,
        "bankFreezeQuantity": 0,
        "niftyFreezeQuantity": 0,
        "finFreezeQuantity": 0,
    }


class BackendTable(Base):

    __tablename__ = "backend_table"
    _DEFAULTS = BackendDefaults.DEFAULT_CONFIG

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, unique=True, index=True)

    bank_quantity = Column(Text, nullable=False, default=_DEFAULTS["bank_quantity"])
    bank_quantity_otm = Column(Text, nullable=False, default=_DEFAULTS["bank_quantity_otm"])
    bank_quantity_atm = Column(Text, nullable=False, default=_DEFAULTS["bank_quantity_atm"])
    bank_quantity_itm = Column(Text, nullable=False, default=_DEFAULTS["bank_quantity_itm"])

    nifty_quantity = Column(Text, nullable=False, default=_DEFAULTS["nifty_quantity"])
    nifty_quantity_otm = Column(Text, nullable=False, default=_DEFAULTS["nifty_quantity_otm"])
    nifty_quantity_atm = Column(Text, nullable=False, default=_DEFAULTS["nifty_quantity_atm"])
    nifty_quantity_itm = Column(Text, nullable=False, default=_DEFAULTS["nifty_quantity_itm"])

    fin_quantity = Column(Text, nullable=False, default=_DEFAULTS["fin_quantity"])
    fin_quantity_otm = Column(Text, nullable=False, default=_DEFAULTS["fin_quantity_otm"])
    fin_quantity_atm = Column(Text, nullable=False, default=_DEFAULTS["fin_quantity_atm"])
    fin_quantity_itm = Column(Text, nullable=False, default=_DEFAULTS["fin_quantity_itm"])

    sensex_quantity = Column(Text, nullable=False, default=_DEFAULTS["sensex_quantity"])
    sensex_quantity_otm = Column(Text, nullable=False, default=_DEFAULTS["sensex_quantity_otm"])
    sensex_quantity_atm = Column(Text, nullable=False, default=_DEFAULTS["sensex_quantity_atm"])
    sensex_quantity_itm = Column(Text, nullable=False, default=_DEFAULTS["sensex_quantity_itm"])

    bankex_quantity = Column(Text, nullable=False, default=_DEFAULTS["bankex_quantity"])
    bankex_quantity_otm = Column(Text, nullable=False, default=_DEFAULTS["bankex_quantity_otm"])
    bankex_quantity_atm = Column(Text, nullable=False, default=_DEFAULTS["bankex_quantity_atm"])
    bankex_quantity_itm = Column(Text, nullable=False, default=_DEFAULTS["bankex_quantity_itm"])

    mid_cp_nifty_quantity = Column(Text, nullable=False, default=_DEFAULTS["mid_cp_nifty_quantity"])
    mid_cp_nifty_quantity_otm = Column(Text, nullable=False, default=_DEFAULTS["mid_cp_nifty_quantity_otm"])
    mid_cp_nifty_quantity_atm = Column(Text, nullable=False, default=_DEFAULTS["mid_cp_nifty_quantity_atm"])
    mid_cp_nifty_quantity_itm = Column(Text, nullable=False, default=_DEFAULTS["mid_cp_nifty_quantity_itm"])

    hotkey_value = Column(Text, nullable=False, default=_DEFAULTS["hotkey_value"])
    hotkey_value_otm = Column(Text, nullable=False, default=_DEFAULTS["hotkey_value_otm"])
    hotkey_value_atm = Column(Text, nullable=False, default=_DEFAULTS["hotkey_value_atm"])
    hotkey_value_itm = Column(Text, nullable=False, default=_DEFAULTS["hotkey_value_itm"])

    bankStrikeCheck = Column(Boolean, nullable=False, default=_DEFAULTS["bankStrikeCheck"])
    niftyStrikeCheck = Column(Boolean, nullable=False, default=_DEFAULTS["niftyStrikeCheck"])
    finStrikeCheck = Column(Boolean, nullable=False, default=_DEFAULTS["finStrikeCheck"])

    bank_strikes = Column(Text, nullable=True, default=_DEFAULTS["bank_strikes"])
    nifty_strikes = Column(Text, nullable=True, default=_DEFAULTS["nifty_strikes"])
    fin_strikes = Column(Text, nullable=True, default=_DEFAULTS["fin_strikes"])

    bankFreezeQuantity = Column(Integer, nullable=False, default=_DEFAULTS["bankFreezeQuantity"])
    niftyFreezeQuantity = Column(Integer, nullable=False, default=_DEFAULTS["niftyFreezeQuantity"])
    finFreezeQuantity = Column(Integer, nullable=False, default=_DEFAULTS["finFreezeQuantity"])
