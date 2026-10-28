"""World Bank World Development Indicators: ~1,500 country series, strong on
demographic breakdowns (male/female, age groups, urban/rural) that OWID often lacks.

Catalog search (by words) -> model picks indicator(s) from the real list ->
download observations. Values come straight from the API.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from ..brief import Intent
from ..dataset import Dataset, DataError, Entity, Source, trim_years
from ..llm import ask
from .common import http, match_names, now_iso

log = logging.getLogger(__name__)
BASE = "https://api.worldbank.org/v2"
STOP = {"the", "in", "of", "vs", "versus", "by", "and", "a", "an", "to", "from", "now", "world", "countries", "country", "number", "total"}


def _pages(path: str, params: dict) -> list[dict]:
    s = http()
    rows: list[dict] = []
    for page in range(1, 12):
        r = s.get(BASE + path, params={**params, "format": "json", "per_page": 20000, "page": page}, timeout=(15, 90))
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
            raise DataError("World Bank returned no table")
        rows += payload[1]
        if page >= int(payload[0].get("pages", 1)):
            return rows
    raise DataError("World Bank result too large")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP}


def candidates(catalog: list[dict], terms: str, limit: int = 30) -> list[dict]:
    query = _words(terms)
    names = [_words(r["name"]) for r in catalog]
    freq = Counter(w for ws in names for w in ws)
    def score(ws):
        return sum(1 + math.log(1 + len(catalog) / (1 + freq[w])) for w in ws & query) - 0.2 * len(ws - query)
    ranked = sorted(zip(catalog, names), key=lambda x: -score(x[1]))
    return [r for r, ws in ranked[:limit] if score(ws) > 0]


class _Pick(BaseModel):
    indicator_id: str
    reason: str


def pick(intent_text: str, options: list[dict]) -> str:
    listing = [{"id": o["id"], "name": o["name"]} for o in options]
    answer = ask(_Pick, "Pick the ONE indicator that measures exactly this (same measure, same units; totals vs "
                        "shares vs rates matter). Use an id from the list, or an empty string if none fits.\n"
                        f"Wanted: {intent_text!r}\nIndicators: {json.dumps(listing)}", max_tokens=200)
    if answer.indicator_id not in {o["id"] for o in options}:
        raise DataError(f"No World Bank indicator matches '{intent_text}'")
    return answer.indicator_id


def _series(indicator: str, country: str, start: int | None, end: int | None) -> dict[int, dict[str, float]]:
    year_now = dt.date.today().year
    rows = _pages(f"/country/{country}/indicator/{indicator}", {"source": 2, "date": f"{start or 1960}:{end or year_now}"})
    out: dict[int, dict[str, float]] = {}
    for r in rows:
        if r.get("value") is None:
            continue
        out.setdefault(int(r["date"]), {})[r["countryiso3code"] or r["country"]["id"]] = float(r["value"])
    return out


def retrieve(intent: Intent, out: Path) -> Dataset:
    catalog = _pages("/indicator", {"source": 2})
    countries = {r["id"]: r for r in _pages("/country", {})}
    names = {r["name"]: cid for cid, r in countries.items()}
    by_id = {r["id"]: r for r in catalog}

    if intent.within and len(intent.subjects) >= 2:
        # groups inside one place: one indicator per group, e.g. "Population, male" / "Population, female"
        place = "WLD" if intent.within.lower() in ("world", "the world", "global") else names[match_names([intent.within], list(names))[intent.within]]
        ids, entities, series = [], [], {}
        for i, subject in enumerate(intent.subjects):
            wanted = f"{intent.metric}, {subject}"
            opts = candidates(catalog, f"{intent.metric} {subject}")
            if not opts:
                raise DataError(f"No World Bank indicator for '{wanted}'")
            ind = pick(wanted, opts)
            ids.append(ind)
            eid = f"E{i}"
            entities.append(Entity(eid, subject.strip().capitalize() if subject.islower() else subject.strip()))
            for y, row in _series(ind, place, intent.start_year, intent.end_year).items():
                for v in row.values():
                    series.setdefault(y, {})[eid] = v
        units = {by_id[i].get("unit", "") for i in ids} - {""}
        if len(units) > 1:
            raise DataError("Chosen indicators use different units")
        series = {y: row for y, row in series.items() if len(row) == len(entities)}
        where = countries[place]["name"]
        title = f"{intent.metric[:1].upper() + intent.metric[1:]} " + ("of the world" if place == "WLD" else f"in {where}")
        notes = "; ".join(f"{by_id[i]['name']} ({i})" for i in ids)
        url = f"https://data.worldbank.org/indicator/{ids[0]}?locations={place}"
    else:
        ind = pick(intent.metric, candidates(catalog, intent.metric) or catalog[:30])
        real = {cid for cid, r in countries.items() if r["region"]["id"] != "NA"}  # NA = aggregates
        if intent.subjects:
            mapping = match_names(intent.subjects, [countries[c]["name"] for c in countries])
            codes = [names[mapping[s]] for s in intent.subjects]
            raw = _series(ind, ";".join(codes), intent.start_year, intent.end_year)
        else:
            raw = _series(ind, "all", intent.start_year, intent.end_year)
            raw = {y: {c: v for c, v in row.items() if c in real} for y, row in raw.items()}
            ever = []
            for y in sorted(raw):
                ever += sorted(raw[y], key=lambda c: -raw[y][c])[:12]
            codes = list(dict.fromkeys(ever))
        ids_map = {c: f"E{i}" for i, c in enumerate(codes)}
        series = {y: {ids_map[c]: v for c, v in row.items() if c in ids_map and v >= 0} for y, row in raw.items()}
        series = {y: r for y, r in series.items() if r}
        entities = [Entity(ids_map[c], countries[c]["name"], countries[c].get("iso2Code", "")) for c in codes]
        title = by_id[ind]["name"].split(" (")[0]
        notes = f"{by_id[ind]['name']} ({ind})"
        url = f"https://data.worldbank.org/indicator/{ind}"
        ids = [ind]
    series = trim_years(series, intent.start_year, intent.end_year)
    unit_raw = by_id[ids[0]]["name"]
    unit = (re.search(r"\(([^)]*)\)\s*$", unit_raw) or [None, ""])[1]
    evidence = [{"subject": e.name, "period": y, "value": row[e.id], "raw": row[e.id], "url": url}
                for y, row in sorted(series.items()) for e in entities if e.id in row]
    (out / "worldbank_choice.json").write_text(json.dumps({"indicators": ids, "notes": notes}, indent=2))
    source = Source(publisher="World Bank", title=notes, url=url, retrieved_at=now_iso(),
                    license="CC BY 4.0 (World Bank Open Data)", notes=notes)
    ds = Dataset(title=title, unit=unit, kind="timeseries", entities=entities, source=source, series=series, evidence=evidence)
    if not intent.over_time:
        from .owid import to_snapshot
        ds = to_snapshot(ds)
    return ds.validate()
