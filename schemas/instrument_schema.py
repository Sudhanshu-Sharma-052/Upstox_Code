from pydantic import BaseModel


class InstrumentSearchRequest(
    BaseModel
):
    search: str