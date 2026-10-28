"""Understand the one-line brief: who is compared, on what, over which years."""
from __future__ import annotations

import datetime as dt
import re
from typing import Literal

from pydantic import BaseModel, Field

from .llm import ask


class Intent(BaseModel):
    metric: str = Field(description="The measure being compared, spelling corrected, e.g. 'GDP per capita'")
    subjects: list[str] = Field(default_factory=list, max_length=15,
                                description="Named subjects in the order given. Empty when the brief asks for a ranking of all countries/items.")
    subject_type: Literal["countries", "other"] = Field(
        description="'countries' for nations, territories, world regions or demographic groups within a country; 'other' for clubs, companies, people, cities, products, etc.")
    within: str | None = Field(None, description="When the subjects are groups inside ONE place (male vs female, age groups, sectors), that place, e.g. 'United States'. Otherwise null.")
    over_time: bool = Field(description="True if the brief asks how things changed over years; False for a current/all-time snapshot")
    start_year: int | None = None
    end_year: int | None = None
    search_queries: list[str] = Field(min_length=1, max_length=4,
                                      description="Short queries to find a dataset or Wikipedia article containing this data")


PROMPT = """You turn a short request for a data video into a structured query.
Request: {brief!r}
Today's year: {year}

Rules:
- Correct spelling. Keep the metric exactly as asked; do not substitute a related metric.
- subjects: only things explicitly named, in the same order. "Countries by X" or "top countries" → subjects = [].
- "Male vs female population in the USA" → subjects ["Male", "Female"], within "United States", metric "population".
- Use common English names ("United States", "China", "FC Barcelona").
- over_time: true when the request gives a year range, says "over time", "history", "since", "race", or the metric naturally changes year to year and no single date is implied.
- search_queries: 2-4 short queries. Include one plain query for the metric alone (e.g. "life expectancy") and, for non-country subjects, one that names the subjects (e.g. "Barcelona Real Madrid honours").
- Never output numbers other than years."""


def _years(brief: str) -> tuple[int | None, int | None]:
    now = dt.date.today().year
    found = [int(y) for y in re.findall(r"\b(1[89]\d{2}|20\d{2})\b", brief)]
    match = re.search(r"\b(?:last|past)\s+(\d{1,3})\s+years?\b", brief, re.I)
    if match:
        return now - int(match.group(1)), now
    match = re.search(r"\bsince\s+(1[89]\d{2}|20\d{2})\b", brief, re.I)
    if match:
        return int(match.group(1)), None
    if len(found) >= 2:
        return min(found), max(found)
    if len(found) == 1:
        return None, found[0]
    return None, None


def understand(brief: str) -> Intent:
    intent = ask(Intent, PROMPT.format(brief=brief, year=dt.date.today().year), max_tokens=500)
    # Years are parsed deterministically from the text and override the model.
    start, end = _years(brief)
    if start or end:
        intent.start_year, intent.end_year = start, end
        intent.over_time = intent.over_time or start is not None
    intent.subjects = list(dict.fromkeys(s.strip() for s in intent.subjects if s.strip()))
    return intent
