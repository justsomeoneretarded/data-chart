"""The single contract between "find data" and "render video".

Every source produces a `Dataset`; every renderer consumes one. A dataset can be
saved to `dataset.json` and re-rendered later without touching the network.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Kind = Literal["timeseries", "snapshot", "categories"]


class DataError(ValueError):
    """Raised when found data is not good enough to make an honest video."""


@dataclass
class Entity:
    id: str
    name: str
    iso2: str = ""  # two-letter country code when the entity is a country (enables flags)


@dataclass
class Source:
    publisher: str
    title: str
    url: str
    retrieved_at: str
    license: str = ""
    notes: str = ""


@dataclass
class Category:
    label: str
    values: dict[str, float]


@dataclass
class Dataset:
    title: str
    unit: str
    kind: Kind
    entities: list[Entity]
    source: Source
    # timeseries: {year: {entity_id: value}}
    series: dict[int, dict[str, float]] = field(default_factory=dict)
    # snapshot: {entity_id: value}
    snapshot: dict[str, float] = field(default_factory=dict)
    as_of: str = ""
    # categories: ordered list of per-category values
    categories: list[Category] = field(default_factory=list)
    # one row per value with the raw source text, written to dataset.csv
    evidence: list[dict] = field(default_factory=list)

    # ---- helpers -------------------------------------------------------
    def name(self, entity_id: str) -> str:
        return self.by_id[entity_id].name

    @property
    def by_id(self) -> dict[str, Entity]:
        return {e.id: e for e in self.entities}

    @property
    def years(self) -> list[int]:
        return sorted(self.series)

    def all_values(self) -> list[float]:
        if self.kind == "timeseries":
            return [v for row in self.series.values() for v in row.values()]
        if self.kind == "snapshot":
            return list(self.snapshot.values())
        return [v for c in self.categories for v in c.values.values()]

    @property
    def integer(self) -> bool:
        values = self.all_values()
        return bool(values) and all(float(v).is_integer() for v in values)

    # ---- validation ----------------------------------------------------
    def validate(self) -> "Dataset":
        if len(self.entities) < 2:
            raise DataError("Need at least two subjects to compare")
        ids = [e.id for e in self.entities]
        if len(set(ids)) != len(ids):
            raise DataError("Duplicate subjects")
        values = self.all_values()
        if not values:
            raise DataError("No values")
        if any(not math.isfinite(v) for v in values):
            raise DataError("Non-finite value in data")
        if any(v < 0 for v in values):
            raise DataError("Negative values cannot be drawn as bars")
        if max(values) <= 0:
            raise DataError("All values are zero")
        if self.kind == "timeseries":
            if len(self.series) < 2:
                raise DataError("A timeline needs at least two years")
            for entity in ids:
                if sum(entity in row for row in self.series.values()) < 2:
                    raise DataError(f"{self.name(entity)} has fewer than two data points")
        if self.kind == "categories" and len(self.categories) < 2:
            raise DataError("Need at least two comparable categories")
        if self.kind == "snapshot" and len(self.snapshot) < 2:
            raise DataError("Need at least two values")
        return self

    # ---- persistence ---------------------------------------------------
    def save(self, out: Path) -> None:
        payload = asdict(self)
        payload["series"] = {str(y): row for y, row in self.series.items()}
        (out / "dataset.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        with (out / "dataset.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["subject", "period_or_category", "value", "source_text", "source_url"])
            for row in self.evidence:
                writer.writerow([row.get("subject"), row.get("period"), row.get("value"), row.get("raw", ""), row.get("url", self.source.url)])

    @classmethod
    def load(cls, path: Path) -> "Dataset":
        raw = json.loads(path.read_text())
        raw["entities"] = [Entity(**e) for e in raw["entities"]]
        raw["source"] = Source(**raw["source"])
        raw["categories"] = [Category(**c) for c in raw.get("categories", [])]
        raw["series"] = {int(y): row for y, row in raw.get("series", {}).items()}
        return cls(**raw)


def trim_years(series: dict[int, dict[str, float]], start: int | None, end: int | None) -> dict[int, dict[str, float]]:
    return {y: row for y, row in series.items() if (start is None or y >= start) and (end is None or y <= end)}
