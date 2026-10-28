"""Common scene structure: header, callout pill, timing."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from ..dataset import Dataset
from .kit import (FPS, H, PALETTE, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP, W, Badges, Formatter, Theme,
                  ease_out, fit, font, mix, rgb, wrap)


@dataclass
class Callout:
    start: float  # seconds
    end: float
    text: str
    color: str


class Scene:
    intro = 1.4   # seconds of build-in at the start
    outro = 3.2   # seconds holding the final state

    def __init__(self, ds: Dataset, theme: Theme, duration: float, badges: Badges, colors: dict[str, str]):
        self.ds = ds
        self.theme = theme
        self.duration = duration
        self.badges = badges
        self.colors = colors
        self.fmt = Formatter(ds.unit, ds.all_values(), ds.integer)
        self.callouts: list[Callout] = []
        self.header_bottom = self._measure_header()

    # ------------------------------------------------------------ timing
    @property
    def frames(self) -> int:
        return int(round(self.duration * FPS))

    @property
    def active(self) -> float:
        return max(1.0, self.duration - self.intro - self.outro)

    def progress(self, t: float) -> float:
        """0 during intro, 0→1 during the active part, 1 during the outro."""
        return min(1.0, max(0.0, (t - self.intro) / self.active))

    # ------------------------------------------------------------ header
    def subtitle(self) -> str:
        return self.ds.unit

    def _measure_header(self) -> int:
        d = ImageDraw.Draw(Image.new("RGB", (W, 10)))
        lines, f = wrap(d, self.ds.title, SAFE_RIGHT - SAFE_LEFT, 84)
        return SAFE_TOP + len(lines) * int(f.size * 1.08) + 96

    def header(self, im: Image.Image, d: ImageDraw.ImageDraw, t: float):
        th = self.theme
        appear = ease_out(t / 0.6)
        lines, f = wrap(d, self.ds.title, SAFE_RIGHT - SAFE_LEFT, 84)
        y = SAFE_TOP + int((1 - appear) * 30)
        ink = mix(th.bg, th.ink, appear)
        for line in lines:
            d.text((SAFE_LEFT, y), line, font=f, fill=ink)
            y += int(f.size * 1.08)
        y += 14
        sub = self.subtitle()
        source = "Source: " + self.ds.source.publisher.split(" — ")[0]
        text = f"{sub}  ·  {source}" if sub else source
        line, sf = fit(d, text, SAFE_RIGHT - SAFE_LEFT, 32, "medium", 22)
        d.text((SAFE_LEFT, y), line, font=sf, fill=mix(th.bg, th.ink2, appear))

    # ------------------------------------------------------------ callouts
    def callout(self, im: Image.Image, d: ImageDraw.ImageDraw, t: float, y: int):
        th = self.theme
        for c in self.callouts:
            if not c.start <= t <= c.end:
                continue
            a = min(ease_out((t - c.start) / 0.35), ease_out((c.end - t) / 0.35))
            text, f = fit(d, c.text, SAFE_RIGHT - SAFE_LEFT - 110, 34, "semibold", 24)
            tw = d.textlength(text, font=f)
            w, h = tw + 96, 66
            x = (W - w) / 2
            yy = y + (1 - a) * 18
            d.rounded_rectangle((x, yy, x + w, yy + h), radius=h // 2,
                                fill=mix(th.bg, th.card, a), outline=mix(th.bg, c.color, a), width=3)
            d.ellipse((x + 26, yy + h / 2 - 9, x + 44, yy + h / 2 + 9), fill=mix(th.bg, c.color, a))
            d.text((x + 62, yy + 15), text, font=f, fill=mix(th.bg, th.ink, a))
            return

    def frame(self, t: float) -> Image.Image:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        im = Image.new("RGB", (W, H), rgb(self.theme.bg))
        return im, ImageDraw.Draw(im)


def assign_colors(ds: Dataset) -> dict[str, str]:
    """Color follows the entity (by its order in the dataset), never its rank."""
    return {e.id: PALETTE[i % len(PALETTE)] for i, e in enumerate(ds.entities)}
