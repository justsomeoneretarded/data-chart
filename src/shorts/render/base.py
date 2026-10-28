"""Common scene structure: header, callout pill, timing."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from ..dataset import Dataset
import math
import random

from .kit import (FPS, H, PALETTE, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP, W, Badges, Formatter, Theme,
                  ease_out, ease_out_back, ellipsize, fit, font, medal, mix, paste, rgb, wrap)


@dataclass
class Winner:
    """Final pop-up banner: gold medal, name, value."""
    entity_id: str
    value_text: str
    note: str = ""  # e.g. "in 2023"


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
        """Only show a unit when the numbers don't already make it obvious ($, %)."""
        if self.fmt.currency or self.fmt.percent:
            return ""
        unit = (self.ds.unit or "").strip()
        if not unit or unit.lower() in self.ds.title.lower():
            return ""
        return unit

    def _measure_header(self) -> int:
        d = ImageDraw.Draw(Image.new("RGB", (W, 10)))
        lines, f = wrap(d, self.ds.title, SAFE_RIGHT - SAFE_LEFT, 84)
        sub = 50 if self.subtitle() else 0
        return SAFE_TOP + len(lines) * int(f.size * 1.08) + sub + 40

    def header(self, im: Image.Image, d: ImageDraw.ImageDraw, t: float):
        th = self.theme
        appear = ease_out(t / 0.6)
        lines, f = wrap(d, self.ds.title, SAFE_RIGHT - SAFE_LEFT, 84)
        y = SAFE_TOP + int((1 - appear) * 30)
        ink = mix(th.bg, th.ink, appear)
        for line in lines:
            d.text(((W - d.textlength(line, font=f)) / 2, y), line, font=f, fill=ink)
            y += int(f.size * 1.08)
        sub = self.subtitle()
        if sub:
            y += 10
            line, sf = fit(d, sub, SAFE_RIGHT - SAFE_LEFT, 32, "medium", 22)
            d.text(((W - d.textlength(line, font=sf)) / 2, y), line, font=sf, fill=mix(th.bg, th.ink2, appear))

    # ------------------------------------------------------------ winner
    winner: Winner | None = None

    def winner_banner(self, im: Image.Image, t: float) -> Image.Image:
        """Pop-up winner card with a gold medal and falling confetti during the final hold."""
        if self.winner is None:
            return im
        start = self.duration - self.outro + 0.15
        if t < start:
            return im
        th = self.theme
        local = t - start
        a = min(1.0, local / 0.35)
        # dim what's behind so the banner reads
        im = Image.blend(im, Image.new("RGB", im.size, rgb(th.bg)), 0.55 * a)
        card = self._banner_card()
        scale = 0.6 + 0.4 * ease_out_back(local / 0.55)
        cw, ch = int(card.width * scale), int(card.height * scale)
        sprite = card.resize((max(1, cw), max(1, ch)), Image.Resampling.BILINEAR)
        cy = 820
        self._confetti(im, local)          # behind the card
        paste(im, sprite, (W - cw) / 2, cy - ch / 2)
        return im

    def _banner_card(self) -> Image.Image:
        if getattr(self, "_card", None) is not None:
            return self._card
        th = self.theme
        w = 860
        gold = "#e0a800"
        probe = ImageDraw.Draw(Image.new("RGB", (w, 10)))
        name = self.ds.name(self.winner.entity_id)
        lines, nf = wrap(probe, name, w - 90, 84, "black", max_lines=2, min_size=46)
        m = medal(1, 200)
        # layout: medal overlaps the card's top edge, then WINNER, name, value, note
        card_top = int(m.height * 0.55)
        y_label = m.height + 18
        y_name = y_label + 74
        y_value = y_name + len(lines) * int(nf.size * 1.1) + 10
        y_note = y_value + 84
        h = (y_note + 56 if self.winner.note else y_value + 100)
        img = Image.new("RGBA", (w, h + 10), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((8, card_top, w - 8, h), radius=44, fill=th.card, outline=gold, width=7)
        paste(img, m, (w - m.width) / 2, 0)
        lf = font(40, "black")
        spaced = "  ".join("WINNER")
        d.text(((w - d.textlength(spaced, font=lf)) / 2, y_label), spaced, font=lf, fill=gold)
        y = y_name
        for line in lines:
            line = ellipsize(d, line, nf, w - 90)
            d.text(((w - d.textlength(line, font=nf)) / 2, y), line, font=nf, fill=th.ink)
            y += int(nf.size * 1.1)
        vf = font(64, "bold")
        d.text(((w - d.textlength(self.winner.value_text, font=vf)) / 2, y_value), self.winner.value_text, font=vf,
               fill=self.colors[self.winner.entity_id])
        if self.winner.note:
            sf = font(34, "medium")
            d.text(((w - d.textlength(self.winner.note, font=sf)) / 2, y_note), self.winner.note, font=sf, fill=th.ink2)
        self._card = img
        return img

    def _confetti(self, im: Image.Image, local: float):
        d = ImageDraw.Draw(im)
        rng = random.Random(7)
        colors = PALETTE[:8] + ["#f2b705"] * 3
        for _ in range(70):
            x0 = rng.uniform(0, W)
            speed = rng.uniform(380, 720)
            delay = rng.uniform(0, 0.9)
            y = -40 + (local - delay) * speed
            if y < -40 or y > H * 0.85:
                continue
            x = x0 + 40 * math.sin(local * rng.uniform(2, 5) + x0)
            ang = local * rng.uniform(3, 9)
            w, h = 22, 10
            dx, dy = math.cos(ang) * w / 2, math.sin(ang) * w / 2
            px, py = -math.sin(ang) * h / 2, math.cos(ang) * h / 2
            d.polygon([(x - dx - px, y - dy - py), (x + dx - px, y + dy - py), (x + dx + px, y + dy + py), (x - dx + px, y - dy + py)],
                      fill=rng.choice(colors))

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
