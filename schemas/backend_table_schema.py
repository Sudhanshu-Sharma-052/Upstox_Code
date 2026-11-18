from pydantic import BaseModel, ConfigDict


class BackendTableUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    bank_quantity: str | None = None
    bank_quantity_otm: str | None = None
    bank_quantity_atm: str | None = None
    bank_quantity_itm: str | None = None

    nifty_quantity: str | None = None
    nifty_quantity_otm: str | None = None
    nifty_quantity_atm: str | None = None
    nifty_quantity_itm: str | None = None

    fin_quantity: str | None = None
    fin_quantity_otm: str | None = None
    fin_quantity_atm: str | None = None
    fin_quantity_itm: str | None = None

    sensex_quantity: str | None = None
    sensex_quantity_otm: str | None = None
    sensex_quantity_atm: str | None = None
    sensex_quantity_itm: str | None = None

    bankex_quantity: str | None = None
    bankex_quantity_otm: str | None = None
    bankex_quantity_atm: str | None = None
    bankex_quantity_itm: str | None = None

    mid_cp_nifty_quantity: str | None = None
    mid_cp_nifty_quantity_otm: str | None = None
    mid_cp_nifty_quantity_atm: str | None = None
    mid_cp_nifty_quantity_itm: str | None = None

    hotkey_value: str | None = None
    hotkey_value_otm: str | None = None
    hotkey_value_atm: str | None = None
    hotkey_value_itm: str | None = None

    bankStrikeCheck: bool | None = None
    niftyStrikeCheck: bool | None = None
    finStrikeCheck: bool | None = None

    bank_strikes: str | None = None
    nifty_strikes: str | None = None
    fin_strikes: str | None = None

    bankFreezeQuantity: int | None = None
    niftyFreezeQuantity: int | None = None
    finFreezeQuantity: int | None = None
