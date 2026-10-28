"""Our World in Data: thousands of country-level time series with a public search API.

Search -> model picks one chart from the real results -> download the chart's
published CSV. Every value in the video is a value from that CSV.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel

from ..brief import Intent
from ..dataset import Dataset, DataError, Entity, Source, trim_years
from ..llm import ask
from .common import http, match_names, now_iso

log = logging.getLogger(__name__)
BASE = "https://ourworldindata.org"
TOP_N = 12  # entities kept for an all-country ranking


def _iso2(code: str) -> str:
    if not code or len(code) != 3 or code.startswith("OWID"):
        return ""
    try:
        import pycountry  # optional dependency
        country = pycountry.countries.get(alpha_3=code)
        return country.alpha_2 if country else ""
    except Exception:
        return ""


def search(queries: list[str], subjects: list[str], out: Path) -> list[dict]:
    s = http()
    charts: dict[str, dict] = {}
    for query in queries:
        params = {"q": query, "hitsPerPage": 12, "type": "charts"}
        try:
            r = s.get(f"{BASE}/api/search", params=params, timeout=(10, 30))
            r.raise_for_status()
            hits = r.json().get("results", [])
        except Exception as exc:
            log.warning("OWID search failed for %r: %s", query, exc)
            hits = []
        for hit in hits:
            if hit.get("type", "chart") != "chart" or not hit.get("slug"):
                continue
            charts.setdefault(hit["slug"], {
                "slug": hit["slug"],
                "title": hit.get("title", ""),
                "subtitle": (hit.get("subtitle") or "")[:160],
                "entities": hit.get("availableEntities", [])[:400],
            })
    if not charts:
        charts = {c["slug"]: c for c in _search_fallback(queries)}
    (out / "owid_search.json").write_text(json.dumps(list(charts.values()), indent=1)[:2_000_000])
    return list(charts.values())


def _search_fallback(queries: list[str]) -> list[dict]:
    """If the OWID API is unreachable, find grapher pages through a general web search."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []
    found = []
    for query in queries[:2]:
        try:
            for r in DDGS(timeout=20).text(f"site:ourworldindata.org/grapher {query}", max_results=8):
                m = re.search(r"ourworldindata\.org/grapher/([a-z0-9-]+)", r.get("href", ""))
                if m:
                    found.append({"slug": m.group(1), "title": r.get("title", "").split("|")[0].strip(), "subtitle": r.get("body", "")[:160], "entities": []})
        except Exception as exc:
            log.warning("Fallback search failed: %s", exc)
    return list({c["slug"]: c for c in found}.values())


class _Pick(BaseModel):
    index: int
    reason: str


def choose_chart(intent: Intent, charts: list[dict]) -> dict:
    options = [{"index": i, "title": c["title"], "subtitle": c["subtitle"]} for i, c in enumerate(charts[:30])]
    pick = ask(
        _Pick,
        "Pick the ONE chart whose measure is exactly what the request asks for (same measure, same units, "
        "same per-capita/total/share framing). If none matches, index = -1.\n"
        f"Request metric: {intent.metric!r}; subjects: {intent.subjects or 'all countries'}\n"
        f"Charts: {json.dumps(options)}",
        max_tokens=200,
    )
    if not 0 <= pick.index < len(options):
        raise DataError(f"No Our World in Data chart matches '{intent.metric}'")
    chosen = charts[pick.index]
    if intent.subjects and chosen["entities"] and not intent.within:
        match_names(intent.subjects, chosen["entities"])  # fail early if subjects are not covered
    return chosen


def _choose_column(intent: Intent, columns: list[str], meta: dict) -> str:
    if len(columns) == 1:
        return columns[0]
    options = [{"index": i, "column": c, "title": (meta.get(c) or {}).get("titleShort", c)} for i, c in enumerate(columns)]
    pick = ask(_Pick, f"Which column measures {intent.metric!r}? Options: {json.dumps(options)}", max_tokens=150)
    if not 0 <= pick.index < len(columns):
        raise DataError("No matching column in chart")
    return columns[pick.index]


def fetch(intent: Intent, chart: dict, out: Path) -> Dataset:
    s = http()
    url = f"{BASE}/grapher/{chart['slug']}"
    params = "?v=1&csvType=full&useColumnShortNames=false"
    csv_resp = s.get(url + ".csv" + params, timeout=(10, 120))
    csv_resp.raise_for_status()
    try:
        meta = s.get(url + ".metadata.json" + params, timeout=(10, 60)).json()
    except Exception:
        meta = {}
    (out / "source_raw.csv").write_text(csv_resp.text)
    (out / "source_metadata.json").write_text(json.dumps(meta, indent=2))

    reader = csv.DictReader(io.StringIO(csv_resp.text))
    fields = reader.fieldnames or []
    if "Year" not in fields or "Entity" not in fields:
        raise DataError("Chart is not yearly country data")
    rows = list(reader)
    value_columns = [f for f in fields if f not in {"Entity", "Code", "Year"} and any(r.get(f) for r in rows[:500])]
    col_meta = meta.get("columns", {}) if isinstance(meta, dict) else {}
    if intent.within and len(value_columns) >= 2:
        return _groups_within_place(intent, chart, rows, value_columns, col_meta, meta, url)
    column = _choose_column(intent, value_columns, col_meta)
    info = col_meta.get(column, {})

    codes: dict[str, str] = {}
    series: dict[int, dict[str, float]] = {}
    for r in rows:
        raw = r.get(column, "")
        if raw in ("", None):
            continue
        try:
            value = float(raw)
            year = int(r["Year"])
        except ValueError:
            continue
        codes[r["Entity"]] = r.get("Code", "")
        series.setdefault(year, {})[r["Entity"]] = value

    series = trim_years(series, intent.start_year, intent.end_year)
    if not series:
        raise DataError("No data in the requested years")

    if intent.subjects:
        mapping = match_names(intent.subjects, sorted(codes))
        keep = [mapping[s] for s in intent.subjects]
    else:
        countries = [e for e, c in codes.items() if len(c) == 3 and c.isalpha()]
        ever_top: list[str] = []
        for year in sorted(series):
            ranked = sorted((e for e in series[year] if e in countries), key=lambda e: -series[year][e])
            ever_top += ranked[:TOP_N]
        keep = list(dict.fromkeys(ever_top))
        if not keep:
            raise DataError("No country rows in chart")

    ids = {name: f"E{i}" for i, name in enumerate(keep)}
    series = {y: {ids[e]: v for e, v in row.items() if e in ids and v >= 0} for y, row in series.items()}
    series = {y: row for y, row in series.items() if row}

    title = info.get("titleShort") or (meta.get("chart") or {}).get("title") or chart["title"]
    unit = info.get("shortUnit") or info.get("unit") or ""
    long_unit = info.get("unit") or unit
    source = Source(
        publisher="Our World in Data — " + (info.get("citationShort") or "see source"),
        title=chart["title"],
        url=url,
        retrieved_at=now_iso(),
        license="CC BY 4.0 (Our World in Data); check underlying source terms",
        notes=(info.get("descriptionShort") or chart.get("subtitle") or "")[:600],
    )
    entities = [Entity(ids[name], name, _iso2(codes.get(name, ""))) for name in keep]
    evidence = [{"subject": e.name, "period": y, "value": row[e.id], "raw": row[e.id], "url": url}
                for y, row in sorted(series.items()) for e in entities if e.id in row]

    ds = Dataset(title=title, unit=long_unit if len(long_unit) <= 24 else unit, kind="timeseries",
                 entities=entities, source=source, series=series, evidence=evidence)
    if not intent.over_time:
        ds = to_snapshot(ds)
    return ds.validate()


def _groups_within_place(intent, chart, rows, columns, col_meta, meta, url) -> Dataset:
    """Subjects are columns (e.g. male / female) of one entity (e.g. United States)."""
    place = match_names([intent.within], sorted({r["Entity"] for r in rows}))[intent.within]
    titles = {(col_meta.get(c) or {}).get("titleShort") or c: c for c in columns}
    mapping = match_names(intent.subjects, list(titles))
    chosen = [titles[mapping[s]] for s in intent.subjects]
    ids = {c: f"E{i}" for i, c in enumerate(chosen)}
    series: dict[int, dict[str, float]] = {}
    for r in rows:
        if r["Entity"] != place:
            continue
        for c in chosen:
            try:
                series.setdefault(int(r["Year"]), {})[ids[c]] = float(r[c])
            except (ValueError, TypeError):
                pass
    series = trim_years(series, intent.start_year, intent.end_year)
    info = col_meta.get(chosen[0], {})
    entities = [Entity(ids[c], s.strip().capitalize() if s.islower() else s) for s, c in zip(intent.subjects, chosen)]
    source = Source(publisher="Our World in Data — " + (info.get("citationShort") or "see source"), title=chart["title"],
                    url=url, retrieved_at=now_iso(), license="CC BY 4.0 (Our World in Data); check underlying source terms",
                    notes=f"{place}. " + (info.get("descriptionShort") or "")[:500])
    evidence = [{"subject": e.name, "period": y, "value": row[e.id], "raw": row[e.id], "url": url}
                for y, row in sorted(series.items()) for e in entities if e.id in row]
    title = f"{intent.metric[:1].upper() + intent.metric[1:]} in {place}"
    ds = Dataset(title=title, unit=info.get("shortUnit") or info.get("unit") or "", kind="timeseries",
                 entities=entities, source=source, series=series, evidence=evidence)
    if not intent.over_time:
        ds = to_snapshot(ds)
    return ds.validate()


def to_snapshot(ds: Dataset) -> Dataset:
    """Latest year in which (nearly) all subjects have a value."""
    need = len(ds.entities) if len(ds.entities) <= 15 else max(2, int(len(ds.entities) * 0.8))
    for year in sorted(ds.series, reverse=True):
        if len(ds.series[year]) >= need:
            row = ds.series[year]
            ds.kind = "snapshot"
            ds.snapshot = dict(row)
            ds.as_of = str(year)
            ds.entities = [e for e in ds.entities if e.id in row]
            ds.evidence = [r for r in ds.evidence if r["period"] == year]
            ds.series = {}
            return ds
    raise DataError("No single year covers all subjects")


def retrieve(intent: Intent, out: Path) -> Dataset:
    queries = list(dict.fromkeys([intent.metric] + intent.search_queries))
    charts = search(queries, intent.subjects, out)
    if not charts:
        raise DataError("Our World in Data search returned nothing")
    chart = choose_chart(intent, charts)
    log.info("OWID chart chosen: %s", chart["slug"])
    return fetch(intent, chart, out)
