# catalog/schemas.py
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TopicRequest(BaseModel):
    query: str


class DatesResponse(BaseModel):
    confirmed: bool
    events: List[date]
    message: str

    @field_validator("events", mode="before")
    def parse_dates(cls, v):
        return [date.fromisoformat(d) if isinstance(d, str) else d for d in v]


class StockRequest(BaseModel):
    stocks: Optional[List[str]]
    top_n: Optional[int]


class StocksBasket(BaseModel):
    positive: List[str] = Field(default_factory=list)
    negative: List[str] = Field(default_factory=list)


class StockResponse(BaseModel):
    stocks: StocksBasket
    message: str


class AnalysisParams(BaseModel):
    title: str
    events: List[date]
    stocks: List[str]  # tickers stored here
    message: str
