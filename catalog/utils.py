# catalog/utils.py
import json

from openai import OpenAI

from catalog.schemas import DatesResponse

# import re


MODEL = "gpt-4o-mini"


def generate_dates(query: str) -> DatesResponse:
    # Build a structured prompt to match the DatesResponse schema
    prompt = (
        f'I want to analyze: "{query}".\n'
        "List the most significant dates of this event.\n"
        "Reply with JSON containing exactly these keys:\n"
        "  confirmed: true if dates found, otherwise false\n"
        "  events: array of dates in ISO format (YYYY-MM-DD)\n"
        "  message: a brief summary sentence.\n"
        "Example format:\n"
        '{"confirmed":true,"events":["2022-05-05"],"message":"Found 1 date."}\n'
    )

    llm = OpenAI()
    raw = (
        llm.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}]
        )
        .choices[0]
        .message.content
    )

    # Extract the JSON substring between the first '{' and the last '}'
    start = raw.find("{")
    end = raw.rfind("}") + 1
    json_text = raw[start:end]

    data = json.loads(json_text)
    return DatesResponse.model_validate(data)
