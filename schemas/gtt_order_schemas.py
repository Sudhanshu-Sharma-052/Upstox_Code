from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class GTTRuleSchema(BaseModel):
    strategy: Literal["ENTRY", "TARGET", "STOPLOSS"]
    trigger_type: Literal["ABOVE", "BELOW", "IMMEDIATE"] = "ABOVE"
    trigger_price: float = Field(default=0, gt=0)
    trailing_gap: Optional[float] = Field(default=None, ge=0)
    market_protection: Optional[float] = -1

    @model_validator(mode="before")
    @classmethod
    def normalize_trailing_gap(cls, values):
        if not isinstance(values, dict):
            return values

        values = values.copy()
        strategy = values.get("strategy")
        trailing_gap = values.get("trailing_gap")

        # ENTRY aur TARGET mein trailing_gap allowed nahi hai.
        # Zero diya ho to ignore kar do.
        if strategy in ("ENTRY", "TARGET"):
            if trailing_gap not in (None, 0):
                raise ValueError(
                    "trailing_gap is only applicable to STOPLOSS"
                )

            values.pop("trailing_gap", None)

        return values

    @model_validator(mode="after")
    def validate_rule(self):
        if self.strategy == "ENTRY":
            if self.trigger_type not in ("ABOVE", "BELOW", "IMMEDIATE"):
                raise ValueError(
                    "ENTRY trigger_type must be ABOVE, BELOW, or IMMEDIATE"
                )

        elif self.strategy in ("TARGET", "STOPLOSS"):
            if self.trigger_type != "IMMEDIATE":
                raise ValueError(
                    "TARGET and STOPLOSS trigger_type must be IMMEDIATE"
                )

        return self


class GTTOrderSchema(BaseModel):
    type: Literal["SINGLE", "MULTIPLE"] = "SINGLE"
    quantity: int = Field(default=0, gt=0)
    product: Literal["I", "D", "MTF"] = "I"
    rules: list[GTTRuleSchema] = Field(default_factory=list)
    instrument_token: str = Field(min_length=1)
    transaction_type: Literal["BUY", "SELL"] = "BUY"

    @model_validator(mode="after")
    def validate_order(self):
        if not self.instrument_token.strip():
            raise ValueError("instrument_token is required")

        if not self.rules:
            raise ValueError("At least one rule is required")

        strategies = [rule.strategy for rule in self.rules]

        if self.type == "SINGLE":
            if len(self.rules) != 1:
                raise ValueError(
                    "SINGLE order must contain exactly one rule"
                )

            if strategies[0] != "ENTRY":
                raise ValueError(
                    "SINGLE order must contain an ENTRY rule"
                )

        elif self.type == "MULTIPLE":
            if not 2 <= len(self.rules) <= 3:
                raise ValueError(
                    "MULTIPLE order must contain 2 or 3 rules"
                )

            if strategies.count("ENTRY") != 1:
                raise ValueError(
                    "MULTIPLE order must contain exactly one ENTRY rule"
                )

            if len(strategies) != len(set(strategies)):
                raise ValueError(
                    "Duplicate strategies are not allowed"
                )

        return self
    
    
class GTTModifyRuleSchema(BaseModel):
    strategy: Literal["ENTRY", "TARGET", "STOPLOSS"]
    trigger_type: Literal["ABOVE", "BELOW", "IMMEDIATE"]
    trigger_price: float = Field(gt=0)
    trailing_gap: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def validate_trailing_gap(cls, values):
        if not isinstance(values, dict):
            return values

        values = values.copy()
        strategy = values.get("strategy")
        gap = values.get("trailing_gap")

        if strategy != "STOPLOSS":
            if gap not in (None, 0):
                raise ValueError(
                    "trailing_gap is only applicable to STOPLOSS"
                )
            values.pop("trailing_gap", None)

        elif gap == 0:
            values.pop("trailing_gap", None)

        return values

    @model_validator(mode="after")
    def validate_trigger_type(self):
        if (
            self.strategy in ("TARGET", "STOPLOSS")
            and self.trigger_type != "IMMEDIATE"
        ):
            raise ValueError(
                "TARGET and STOPLOSS must use IMMEDIATE trigger_type"
            )

        return self


class GTTModifySchema(BaseModel):
    type: Literal["SINGLE", "MULTIPLE"]
    quantity: int = Field(gt=0)
    rules: list[GTTModifyRuleSchema] = Field(min_length=1, max_length=3)
    gtt_order_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_order(self):
        if not self.gtt_order_id.strip():
            raise ValueError("gtt_order_id is required")

        strategies = [rule.strategy for rule in self.rules]

        if strategies.count("ENTRY") != 1:
            raise ValueError(
                "Exactly one ENTRY rule is required"
            )

        if len(strategies) != len(set(strategies)):
            raise ValueError("Duplicate strategies are not allowed")

        if self.type == "SINGLE":
            if len(self.rules) != 1 or strategies[0] != "ENTRY":
                raise ValueError(
                    "SINGLE order must contain exactly one ENTRY rule"
                )

        if self.type == "MULTIPLE" and len(self.rules) < 2:
            raise ValueError(
                "MULTIPLE order must contain at least two rules"
            )

        return self


class GTTCancelSchema(BaseModel):
    gtt_order_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_gtt_order_id(self):
        if not self.gtt_order_id.strip():
            raise ValueError("gtt_order_id is required")

        return self
