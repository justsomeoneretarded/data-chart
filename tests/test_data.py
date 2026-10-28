import json

import pytest

from shorts.brief import Intent, _years
from shorts.dataset import DataError, Dataset, Entity, Source
from shorts.sources import common, owid, wikipedia
from shorts.sources.common import parse_number

SRC = Source("x", "x", "https://example.org", "2026-01-01")


@pytest.mark.parametrize("cell,value", [
    ("1,234", 1234), ("12.5%", 12.5), ("$3.2 billion", 3.2e9), ("45[a]", 45), ("−3", -3), ("—", None), ("", None), ("n/a", None),
])
def test_parse_number(cell, value):
    assert parse_number(cell) == value


def test_years_from_brief():
    assert _years("India vs China population, 1960–2025") == (1960, 2025)
    assert _years("GDP since 1990")[0] == 1990
    assert _years("Countries by life expectancy") == (None, None)


def test_dataset_rejects_bad_data():
    ents = [Entity("A", "a"), Entity("B", "b")]
    with pytest.raises(DataError):
        Dataset("t", "u", "snapshot", ents[:1], SRC, snapshot={"A": 1}).validate()
    with pytest.raises(DataError):
        Dataset("t", "u", "snapshot", ents, SRC, snapshot={"A": 1, "B": float("nan")}).validate()
    with pytest.raises(DataError):
        Dataset("t", "u", "timeseries", ents, SRC, series={2000: {"A": 1, "B": 2}}).validate()


def test_dataset_roundtrip(tmp_path):
    ds = Dataset("t", "u", "timeseries", [Entity("A", "a"), Entity("B", "b")], SRC,
                 series={2000: {"A": 1, "B": 2}, 2001: {"A": 3, "B": 1}}).validate()
    ds.save(tmp_path)
    again = Dataset.load(tmp_path / "dataset.json")
    assert again.series == ds.series and again.entities == ds.entities


# ------------------------------------------------------------ Wikipedia
def _tables():
    return wikipedia.tables_from("El Clásico", open("tests/fixtures/honours.html").read(), "A0")


def test_wikipedia_table_extraction_handles_spans_and_footnotes():
    tables = _tables()
    assert len(tables) == 2
    honours = tables[0]
    assert honours.header == ["Competition", "Titles Barcelona", "Titles Real Madrid"]
    assert honours.rows[0] == ["La Liga", "27", "36"]


def test_wikipedia_categories_build(monkeypatch):
    monkeypatch.setattr(common, "ask", lambda *a, **k: pytest.fail("names should match without the model"))
    t = _tables()[0]
    t.header = ["Competition", "Barcelona", "Real Madrid"]
    spec = wikipedia.TableSpec(table_id=t.id, layout="categories_by_subject_columns", category_column=0, columns=[1, 2],
                               title="Trophies", unit="trophies")
    intent = Intent(metric="trophies", subjects=["FC Barcelona", "Real Madrid"], subject_type="other", over_time=False, search_queries=["x"])
    ds = wikipedia.build(spec, t, intent)
    assert ds.kind == "categories"
    assert [c.label for c in ds.categories][:2] == ["La Liga", "Copa del Rey"]
    assert "Total" not in [c.label for c in ds.categories]  # total rows are not a category
    assert ds.categories[0].values == {"E0": 27, "E1": 36}


def test_wikipedia_years_build():
    t = _tables()[1]
    spec = wikipedia.TableSpec(table_id=t.id, layout="years_by_subject_columns", year_column=0, columns=[1, 2], title="Attendance", unit="fans")
    intent = Intent(metric="attendance", subjects=[], subject_type="other", over_time=True, search_queries=["x"])
    ds = wikipedia.build(spec, t, intent)
    assert ds.kind == "timeseries"
    assert ds.years == [2018, 2019, 2021]  # missing season skipped, not zero-filled
    assert all(e["raw"] for e in ds.evidence)


def test_wikipedia_rejects_bad_columns():
    t = _tables()[0]
    spec = wikipedia.TableSpec(table_id=t.id, layout="ranking", subject_column=0, value_column=9, title="x", unit="x")
    with pytest.raises(DataError):
        wikipedia.build(spec, t, Intent(metric="x", subject_type="other", over_time=False, search_queries=["x"]))


# ------------------------------------------------------------ OWID
CSV = """Entity,Code,Year,Life expectancy
India,IND,2000,62.5
India,IND,2001,63.0
China,CHN,2000,71.4
China,CHN,2001,71.8
World,OWID_WRL,2000,67.0
World,OWID_WRL,2001,67.3
"""


class FakeResp:
    def __init__(self, text="", data=None):
        self.text, self._data = text, data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeSession:
    def get(self, url, params=None, timeout=None):
        if "/api/search" in url:
            return FakeResp(data={"results": [
                {"slug": "life-expectancy", "title": "Life expectancy", "type": "chart", "availableEntities": ["India", "China", "World"]},
                {"slug": "gdp", "title": "GDP", "type": "chart", "availableEntities": []}]})
        if url.endswith(".csv?v=1&csvType=full&useColumnShortNames=false"):
            return FakeResp(CSV)
        return FakeResp(data={"columns": {"Life expectancy": {"titleShort": "Life expectancy", "unit": "years", "citationShort": "UN WPP"}}})


def test_owid_country_versus(monkeypatch, tmp_path):
    monkeypatch.setattr(owid, "http", lambda: FakeSession())
    monkeypatch.setattr(owid, "ask", lambda schema, prompt, **k: schema(index=0, reason="match"))
    intent = Intent(metric="life expectancy", subjects=["India", "China"], subject_type="countries", over_time=True, search_queries=["life expectancy"])
    ds = owid.retrieve(intent, tmp_path)
    assert ds.kind == "timeseries" and ds.unit == "years"
    assert [e.name for e in ds.entities] == ["India", "China"]
    assert ds.series[2001] == {"E0": 63.0, "E1": 71.8}
    assert (tmp_path / "source_raw.csv").exists()


def test_owid_ranking_excludes_aggregates(monkeypatch, tmp_path):
    monkeypatch.setattr(owid, "http", lambda: FakeSession())
    monkeypatch.setattr(owid, "ask", lambda schema, prompt, **k: schema(index=0, reason="match"))
    intent = Intent(metric="life expectancy", subjects=[], subject_type="countries", over_time=False, search_queries=["x"])
    ds = owid.retrieve(intent, tmp_path)
    assert ds.kind == "snapshot" and ds.as_of == "2001"
    assert "World" not in [e.name for e in ds.entities]


def test_owid_no_matching_chart(monkeypatch, tmp_path):
    monkeypatch.setattr(owid, "http", lambda: FakeSession())
    monkeypatch.setattr(owid, "ask", lambda schema, prompt, **k: schema(index=-1, reason="none"))
    intent = Intent(metric="happiness of cats", subjects=[], subject_type="countries", over_time=False, search_queries=["x"])
    with pytest.raises(DataError):
        owid.retrieve(intent, tmp_path)


def test_from_year_to_now():
    assert _years("male vs female population in the world from 1950 to now") == (1950, None)
    assert _years("GDP 1990-present") == (1990, None)
    assert _years("Population in 2020") == (None, 2020)


SEX_CSV = {
    "male-population": "Entity,Code,Year,Male population\nWorld,OWID_WRL,1950,1260000000\nWorld,OWID_WRL,2023,4060000000\nIndia,IND,1950,190000000\n",
    "female-population": "Entity,Code,Year,Female population\nWorld,OWID_WRL,1950,1270000000\nWorld,OWID_WRL,2023,4030000000\n",
}


class SexSession:
    def get(self, url, params=None, timeout=None):
        if "/api/search" in url:
            q = params["q"].lower()
            slug = "female-population" if "female" in q else "male-population"
            return FakeResp(data={"results": [{"slug": slug, "title": slug.replace("-", " ").capitalize(), "type": "chart", "availableEntities": ["World"]}]})
        for slug, text in SEX_CSV.items():
            if f"/grapher/{slug}.csv" in url:
                return FakeResp(text)
        return FakeResp(data={})


def test_owid_groups_from_separate_charts(monkeypatch, tmp_path):
    monkeypatch.setattr(owid, "http", lambda: SexSession())
    monkeypatch.setattr(owid, "ask", lambda schema, prompt, **k: schema(index=0, reason="match"))
    monkeypatch.setattr(common, "ask", lambda schema, prompt, **k: schema(matches=["World"]))
    intent = Intent(metric="population", subjects=["Male", "Female"], within="World", subject_type="countries",
                    over_time=True, start_year=1950, search_queries=["population by sex"])
    ds = owid.retrieve(intent, tmp_path)
    assert [e.name for e in ds.entities] == ["Male", "Female"]
    assert ds.series[2023] == {"E0": 4060000000.0, "E1": 4030000000.0}
    assert ds.title == "World population"
