import json
import subprocess

import pytest

import fixtures_data as fx
from shorts.main import parser, run
from shorts.render import choose_layout
from shorts.render.base import assign_colors
from shorts.render.kit import THEMES, Badges, Formatter


@pytest.mark.parametrize("name,layout", [("race", "Race"), ("countdown", "Countdown"), ("versus", "VersusTimeline"), ("categories", "VersusCategories")])
def test_every_layout_draws(tmp_path, name, layout, monkeypatch):
    monkeypatch.setenv("SHORTS_OFFLINE", "1")
    ds = getattr(fx, name)()
    cls = choose_layout(ds)
    assert cls.__name__ == layout
    colors = assign_colors(ds)
    scene = cls(ds, THEMES["Light"], 30, Badges(ds.entities, colors, tmp_path, THEMES["Light"]), colors)
    first, mid, last = (scene.frame(t) for t in (0.0, 15.0, 29.9))
    assert first.size == (1080, 1920)
    assert first.tobytes() != mid.tobytes() != last.tobytes()


def test_colors_follow_entities_not_rank():
    ds = fx.race()
    assert assign_colors(ds)["E0"] == assign_colors(ds)["E0"]
    assert len(set(assign_colors(ds).values())) == len(ds.entities)


def test_formatter():
    assert Formatter("current US$", [1e12], False)(2.345e12) == "$2.35T"
    assert Formatter("%", [50], False)(12.34) == "12.3%"
    assert Formatter("trophies", [36], True)(36) == "36"
    assert Formatter("people", [1e9], False)(0) == "0"


def test_full_video_from_dataset(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_OFFLINE", "1")
    fx.versus().save(tmp_path)
    out = tmp_path / "out"
    args = parser().parse_args(["--dataset", str(tmp_path / "dataset.json"), "--out", str(out), "--duration", "30", "--preview"])
    assert run(args) == 0
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(out / "video.mp4")],
                                      capture_output=True, text=True, check=True).stdout)
    assert abs(float(probe["format"]["duration"]) - 30) < 1
    assert json.loads((out / "quality_report.json").read_text())["passed"]
    assert (out / "thumbnail.png").exists() and (out / "metadata.json").exists()


def test_no_data_means_no_video(tmp_path, monkeypatch):
    from shorts import brief, sources
    from shorts.dataset import DataError

    monkeypatch.setattr(brief, "understand", lambda b: brief.Intent(metric="x", subject_type="other", over_time=False, search_queries=["x"]))
    def nothing(*a, **k):
        raise DataError("nothing found")
    monkeypatch.setattr(sources, "resolve", nothing)
    args = parser().parse_args(["--brief", "favourite colours of cats", "--out", str(tmp_path)])
    assert run(args) == 1
    assert not (tmp_path / "video.mp4").exists()
    assert "nothing was invented" in (tmp_path / "production_report.md").read_text()


def test_auto_duration_follows_the_data():
    from shorts.render import auto_duration
    assert auto_duration(fx.race()) == 34          # 33 years of race
    assert auto_duration(fx.countdown()) == 33     # 10 reveals
    assert auto_duration(fx.categories()) == 30    # short content is held at the 30s minimum
    long = fx.race()
    long.series = {y + 1900 - 1990: row for y, row in long.series.items()} | long.series
    assert auto_duration(long) == 90               # long histories are capped


def test_duration_input_accepts_auto_and_rejects_nonsense(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_OFFLINE", "1")
    fx.countdown().save(tmp_path)
    args = parser().parse_args(["--dataset", str(tmp_path / "dataset.json"), "--out", str(tmp_path / "bad"), "--duration", "soon"])
    assert run(args) == 1
    assert parser().parse_args([]).duration == "Auto"


@pytest.mark.parametrize("name", ["countdown", "categories"])
def test_full_pipeline_passes_quality_check_at_default_length(tmp_path, monkeypatch, name):
    """Layouts with reveals must never sit frozen long enough to fail the check (bug seen in CI)."""
    monkeypatch.setenv("SHORTS_OFFLINE", "1")
    getattr(fx, name)().save(tmp_path)
    args = parser().parse_args(["--dataset", str(tmp_path / "dataset.json"), "--out", str(tmp_path / "o"), "--duration", "50", "--music", "None"])
    assert run(args) == 0, (tmp_path / "o" / "failure.json").read_text()


def test_long_typed_duration_is_capped_for_few_items(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_OFFLINE", "1")
    fx.categories().save(tmp_path)
    args = parser().parse_args(["--dataset", str(tmp_path / "dataset.json"), "--out", str(tmp_path / "o"), "--duration", "90", "--music", "None"])
    assert run(args) == 0, (tmp_path / "o" / "failure.json").read_text()
    assert "capped" in (tmp_path / "o" / "production_report.md").read_text()
