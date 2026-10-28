"""Pick a layout for the data and encode the video."""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from ..dataset import Category, Dataset
from .base import assign_colors
from .kit import FPS, H, THEMES, W, Badges
from .race import Countdown, Race
from .versus import VersusCategories, VersusTimeline

log = logging.getLogger(__name__)


def choose_layout(ds: Dataset, requested: str = "Auto"):
    """The data's shape decides the layout; the user's format choice only breaks ties."""
    two = len(ds.entities) == 2
    if ds.kind == "timeseries":
        if two and requested != "Race":
            return VersusTimeline
        return Race
    if ds.kind == "categories":
        if two:
            return VersusCategories
        # >2 subjects across categories: rank by the sum of the listed categories.
        totals = {e.id: sum(c.values.get(e.id, 0) for c in ds.categories) for e in ds.entities}
        ds.kind, ds.snapshot = "snapshot", totals
        ds.unit = f"{ds.unit} (total of {len(ds.categories)} categories)".strip()
        return Countdown
    if two and requested != "Race":
        ds.kind, ds.categories = "categories", [Category(ds.title, dict(ds.snapshot))]
        return VersusCategories
    return Countdown


def auto_duration(ds: Dataset, fmt: str = "Auto") -> int:
    """Size the video to its content: enough time per year / item to follow, within 30-90s."""
    layout = choose_layout(ds, fmt)
    fixed = 4.6  # intro + final hold
    if ds.kind == "timeseries":
        years = ds.years[-1] - ds.years[0]
        per_year = 0.55 if layout is VersusTimeline else 0.9  # races have more to read per year
        active = years * per_year
    elif layout is VersusCategories:
        active = len(ds.categories[:VersusCategories.MAX_ROWS]) * 3.5
    else:  # countdown
        active = min(10, len(ds.snapshot)) * 2.8
    return int(round(min(90, max(30, active + fixed))))


def render(ds: Dataset, out: Path, *, duration: int = 50, fmt: str = "Auto", theme: str = "Light",
           music: str = "Auto", seed: int = 42, preview: bool = False) -> dict:
    from ..music import prepare
    layout = choose_layout(ds, fmt)
    th = THEMES.get(theme, THEMES["Light"])
    colors = assign_colors(ds)
    badges = Badges(ds.entities, colors, out, th)
    scene = layout(ds, th, duration, badges, colors)
    size = (540, 960) if preview else (W, H)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
           "-r", str(FPS), "-i", "pipe:0"]
    if music == "None":
        audio = {"source": "none"}
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    else:
        audio = prepare(out, duration, seed, music)
        cmd += ["-i", str(out / "music.wav")]
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-t", str(duration), "-movflags", "+faststart", str(out / "video.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    thumb_t = duration - 0.6
    try:
        for i in range(scene.frames):
            t = i / FPS
            im = scene.frame(t)
            if abs(t - thumb_t) < 0.5 / FPS:
                im.save(out / "thumbnail.png")
            if preview:
                im = im.resize(size)
            proc.stdin.write(im.tobytes())
            if i % (FPS * 10) == 0:
                log.info("Rendered %ds / %ds", i // FPS, duration)
        proc.stdin.close()
        if proc.wait(timeout=600):
            raise RuntimeError("FFmpeg failed to encode the video")
    except BaseException:
        proc.kill()
        raise
    if not (out / "thumbnail.png").exists():
        scene.frame(thumb_t).save(out / "thumbnail.png")
    report = {"layout": layout.__name__, "theme": th.name, "audio": audio, "duration": duration,
              "callouts": [c.__dict__ for c in scene.callouts]}
    (out / "render_report.json").write_text(json.dumps(report, indent=2))
    return report
