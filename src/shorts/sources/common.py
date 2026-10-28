"""Helpers shared by all sources: HTTP, name matching, numbers."""
from __future__ import annotations

import datetime as dt
import difflib
import re

import requests
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..dataset import DataError
from ..llm import ask

USER_AGENT = "data-chart-shorts/2.0 (https://github.com/justsomeoneretarded/data-chart)"


def http() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _norm(text: str) -> str:
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text.casefold())
    text = re.sub(r"\b(the|fc|cf|club|de|republic|rep|of)\b", " ", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


class _Mapping(BaseModel):
    matches: list[str]


def match_names(wanted: list[str], available: list[str]) -> dict[str, str]:
    """Map each requested name to one available name. Raises if any cannot be matched."""
    result: dict[str, str] = {}
    unresolved: list[str] = []
    norm_available = {_norm(a): a for a in available}
    for name in wanted:
        n = _norm(name)
        if n in norm_available:
            result[name] = norm_available[n]
            continue
        close = difflib.get_close_matches(n, list(norm_available), n=1, cutoff=0.88)
        if close:
            result[name] = norm_available[close[0]]
        else:
            unresolved.append(name)
    if unresolved:
        # Let the model resolve aliases ("USA" -> "United States"), but only to listed names.
        shortlist: list[str] = []
        for name in unresolved:
            n = _norm(name)
            shortlist += [norm_available[c] for c in difflib.get_close_matches(n, list(norm_available), n=12, cutoff=0.3)]
            shortlist += [a for a in available if n and (n in _norm(a) or _norm(a) in n)][:12]
        shortlist = list(dict.fromkeys(shortlist + available[:60]))[:150]
        answer = ask(
            _Mapping,
            "Map each requested name to the item in the list that means the same thing (aliases, abbreviations, "
            "official names). Use the exact list text, or an empty string if nothing matches.\n"
            f"Requested: {unresolved}\nList: {shortlist}\nReturn matches in the same order as requested.",
            max_tokens=300,
        )
        for name, pick in zip(unresolved, answer.matches):
            if pick in available:
                result[name] = pick
    missing = [n for n in wanted if n not in result]
    if missing:
        raise DataError(f"Could not find {missing} in this source")
    if len(set(result.values())) != len(result):
        raise DataError("Two requested subjects matched the same source entry")
    return result


NUMBER = re.compile(r"[-+]?\d[\d,  ]*(?:\.\d+)?")
SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "mn": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "trillion": 1e12, "t": 1e12}


def parse_number(cell: str) -> float | None:
    """Parse a number from a table cell ("1,234", "12.5%", "$3.2 billion", "45[a]"). Returns None if absent."""
    text = re.sub(r"\[[^\]]*\]", "", cell)  # footnotes
    text = text.replace("−", "-").replace("–", "-").strip()
    if not text or text in {"-", "—", "n/a", "N/A", "?"}:
        return None
    match = NUMBER.search(text)
    if not match:
        return None
    # Reject ranges/dates like "1990–2000" being read as one number
    value = float(re.sub(r"[,  ]", "", match.group()))
    rest = text[match.end():].strip().casefold()
    word = re.match(r"(thousand|million|billion|trillion|mn|bn|[kmbt])\b", rest)
    if word:
        value *= SCALE[word.group(1)]
    return value
