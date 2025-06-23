"""
catalog/utils.py
Utility helpers for the event-analysis flow.

Functions
---------
generate_dates(query: str)  -> DatesResponse
generate_stocks(topic: str) -> StockResponse
"""

from __future__ import annotations

import json
import re

from openai import OpenAI
from pydantic import ValidationError

from catalog.schemas import DatesResponse, StockResponse

# ---------- OpenAI client ----------------------------------------------------

_MODEL = "gpt-4o-mini"
_client = OpenAI()

# ---------- helpers ----------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _strip_fence(text: str) -> str:
    """Remove ```json … ``` fences so the string parses as pure JSON."""
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text.strip()


def _chat(prompt: str) -> str:
    """
    Minimal wrapper around the chat-completion call.
    Returns the assistant’s raw content string.
    """
    resp = _client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


# ---------- public API -------------------------------------------------------


def generate_dates(query: str) -> DatesResponse:
    """
    Ask the LLM for significant dates related to *query* and
    validate the answer against our DatesResponse schema.
    """
    prompt = (
        f"I want to analyse the event or topic: '{query}'.\n"
        "List up to 8 significant dates (ISO-8601 YYYY-MM-DD).\n"
        "Reply *only* with JSON containing exactly these keys:\n"
        '  "confirmed": boolean   # true if dates found\n'
        '  "events":    string[]  # the dates, earliest→latest\n'
        '  "message":   string    # brief summary\n'
        "Example:\n"
        '{"confirmed": true, "events": ["2025-01-01"], '
        '"message": "Found 1 date."}'
    )

    cleaned = _strip_fence(_chat(prompt))
    try:
        data = json.loads(cleaned)
        return DatesResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        # Fallback so callers don’t crash
        return DatesResponse.model_validate(
            {"confirmed": False, "events": [], "message": "Model response invalid"}
        )


def generate_stocks(topic: str, limit: int | None = None) -> StockResponse:
    """
    Ask the LLM for tickers that could move on *topic*:
    - 'positive': likely to go up
    - 'negative': likely to go down or hedge
    """
    prompt = (
        f"Suggest up to 6 liquid US-listed tickers that historically react to news "
        f"about: '{topic}'.\n"
        "Return JSON exactly like:\n"
        "{\n"
        '  "stocks": {\n'
        '    "positive": ["TICK1", "TICK2"],\n'
        '    "negative": ["TICK3", "TICK4"]\n'
        "  },\n"
        '  "message": "short rationale"\n'
        "}"
    )

    cleaned = _strip_fence(_chat(prompt))
    try:
        data = json.loads(cleaned)

        # Safety net if the model returned a plain list
        if isinstance(data.get("stocks"), list):
            data["stocks"] = {"positive": data["stocks"], "negative": []}

        resp = StockResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        resp = StockResponse.model_validate(
            {
                "stocks": {"positive": [], "negative": []},
                "message": "Model response invalid",
            }
        )

    # Apply optional limit per side
    if limit is not None:
        resp.stocks.positive = resp.stocks.positive[:limit]
        resp.stocks.negative = resp.stocks.negative[:limit]

    return resp
