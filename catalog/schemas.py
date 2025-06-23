from datetime import date
from typing import List, Optional

from pydantic import BaseModel, validator


class TopicRequest(BaseModel):
    query: str


class DatesResponse(BaseModel):
    confirmed: bool
    events: List[date]
    message: str

    @validator("events", pre=True, each_item=True)
    def parse_date(cls, v):
        return date.fromisoformat(v) if isinstance(v, str) else v


class StockRequest(BaseModel):
    stocks: Optional[List[str]]
    top_n: Optional[int]


class StockResponse(BaseModel):
    stocks: List[str]
    message: str


class AnalysisParams(BaseModel):
    title: str
    events: List[date]
    stocks: List[str]
    message: str
