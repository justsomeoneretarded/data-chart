"""Synthetic datasets for renderer tests only (not real figures)."""
import math
from shorts.dataset import Category, Dataset, Entity, Source

SRC = Source("Test fixture", "Synthetic data", "https://example.org", "2026-01-01T00:00:00+00:00")
NAMES = [("United States", "us"), ("China", "cn"), ("Japan", "jp"), ("Germany", "de"), ("India", "in"),
         ("United Kingdom", "gb"), ("France", "fr"), ("Italy", "it"), ("Brazil", "br"), ("Canada", "ca"),
         ("Russia", "ru"), ("South Korea", "kr")]

def race():
    ents = [Entity(f"E{i}", n, iso) for i, (n, iso) in enumerate(NAMES)]
    base = [5.9, 0.4, 4.9, 2.0, 0.3, 1.2, 1.4, 1.1, 0.7, 0.7, 0.3, 0.5]
    growth = [0.045, 0.14, 0.008, 0.03, 0.11, 0.035, 0.03, 0.02, 0.07, 0.04, 0.09, 0.06]
    series = {}
    for y in range(1990, 2024):
        k = y - 1990
        series[y] = {f"E{i}": round(b * 1e12 * math.exp(g * k) * (1 + 0.04 * math.sin(k + i)), -8) for i, (b, g) in enumerate(zip(base, growth))}
    return Dataset("GDP of the world's largest economies", "current US$", "timeseries", ents, SRC, series=series).validate()

def countdown():
    ents = [Entity(f"E{i}", n, iso) for i, (n, iso) in enumerate(NAMES[:10])]
    snap = {f"E{i}": v for i, v in enumerate([83.1, 78.2, 84.5, 81.0, 70.8, 81.3, 82.5, 83.5, 75.9, 82.6])}
    return Dataset("Life expectancy at birth", "years", "snapshot", ents, SRC, snapshot=snap, as_of="2023").validate()

def versus():
    ents = [Entity("E0", "India", "in"), Entity("E1", "China", "cn")]
    series = {y: {"E0": 870e6 * math.exp(0.0165 * (y - 1990)) + (0 if y < 2015 else 0), "E1": 1140e6 + 220e6 * (1 - math.exp(-(y - 1990) / 14)) - (0 if y < 2020 else 4e6 * (y - 2020) ** 2)} for y in range(1990, 2025)}
    return Dataset("Population of India vs China", "people", "timeseries", ents, SRC, series=series).validate()

def categories():
    ents = [Entity("E0", "FC Barcelona"), Entity("E1", "Real Madrid")]
    rows = [("La Liga", 27, 36), ("Copa del Rey", 31, 20), ("Champions League", 5, 15), ("Supercopa", 15, 13), ("UEFA Super Cup", 5, 6), ("Club World Cup", 3, 5)]
    cats = [Category(l, {"E0": a, "E1": b}) for l, a, b in rows]
    return Dataset("Barcelona vs Real Madrid trophies", "trophies", "categories", ents, SRC, categories=cats).validate()

def films():
    """Long names and close values, like 'Highest-grossing films of all time' (test numbers)."""
    rows = [("Avatar", 2.92e9), ("Avengers: Endgame", 2.80e9), ("Avatar: The Way of Water", 2.32e9), ("Titanic", 2.26e9),
            ("Ne Zha 2", 2.2e9), ("Star Wars: The Force Awakens", 2.07e9), ("Avengers: Infinity War", 2.05e9),
            ("Spider-Man: No Way Home", 1.92e9), ("Inside Out 2", 1.70e9), ("Jurassic World", 1.67e9)]
    ents = [Entity(f"E{i}", n) for i, (n, _) in enumerate(rows)]
    return Dataset("Highest-grossing films of all time", "worldwide gross (US$)", "snapshot", ents, SRC,
                   snapshot={f"E{i}": v for i, (_, v) in enumerate(rows)}).validate()
