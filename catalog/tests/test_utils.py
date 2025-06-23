import os

import pytest

from catalog.schemas import DatesResponse
from catalog.utils import generate_dates


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No OPENAI_API_KEY in .env")
def test_generate_dates_smoke():
    prompt = "List 1 date of a solar eclipse after 2023-01-01 in JSON."
    resp = generate_dates(prompt)
    assert isinstance(resp, DatesResponse)
    assert len(resp.events) == 1
    assert hasattr(resp.events[0], "year")
