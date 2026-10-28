"""Find the moments worth pointing out in any dataset (overtakes, records, the gap at the end).

These become on-screen callouts, so every video tells a small story without narration.
Everything here is computed from the data; nothing is generated.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dataset import Dataset


@dataclass
class Moment:
    year: float
    text: str
    entity_id: str
    weight: float


class Interp:
    """Piecewise-linear value of each entity at any (fractional) year, None outside its data."""

    def __init__(self, ds: Dataset):
        self.points: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for e in ds.entities:
            pts = sorted((y, row[e.id]) for y, row in ds.series.items() if e.id in row)
            if pts:
                self.points[e.id] = (np.array([p[0] for p in pts], float), np.array([p[1] for p in pts], float))

    def at(self, year: float) -> dict[str, float]:
        out = {}
        for eid, (xs, ys) in self.points.items():
            if xs[0] - 1e-9 <= year <= xs[-1] + 1e-9:
                out[eid] = float(np.interp(year, xs, ys))
        return out


def moments(ds: Dataset, max_count: int = 4) -> list[Moment]:
    if ds.kind != "timeseries":
        return []
    interp = Interp(ds)
    years = ds.years
    found: list[Moment] = []
    leader = None
    # Sample finely so overtakes between annual points are dated sensibly.
    for year in np.linspace(years[0], years[-1], max(2, (years[-1] - years[0]) * 4 + 1)):
        values = interp.at(year)
        if len(values) < 2:
            continue
        top = max(values, key=values.get)
        if leader and top != leader and leader in values:
            if values[top] < values[leader] * 1.01:
                continue  # not a clear overtake yet; avoid flip-flopping on near-ties
            found.append(Moment(year, f"{ds.name(top)} overtakes {ds.name(leader)}", top, 3.0))
        leader = top
    # Biggest single-year jump by any entity (only if notable)
    best = None
    for eid, (xs, ys) in interp.points.items():
        for i in range(1, len(xs)):
            if ys[i - 1] > 0 and xs[i] - xs[i - 1] <= 1.5:
                change = (ys[i] - ys[i - 1]) / ys[i - 1]
                if best is None or abs(change) > abs(best[0]):
                    best = (change, eid, xs[i])
    if best and abs(best[0]) >= 0.25:
        change, eid, year = best
        word = "jumps" if change > 0 else "drops"
        found.append(Moment(year, f"{ds.name(eid)} {word} {abs(change) * 100:.0f}% in {int(year)}", eid, 1.0))
    # Keep the strongest, spread out in time.
    found.sort(key=lambda m: -m.weight)
    span = max(1, years[-1] - years[0])
    chosen: list[Moment] = []
    for m in found:
        if all(abs(m.year - c.year) > span * 0.14 for c in chosen):
            chosen.append(m)
        if len(chosen) >= max_count:
            break
    return sorted(chosen, key=lambda m: m.year)
