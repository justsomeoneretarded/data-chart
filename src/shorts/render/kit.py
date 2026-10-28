"""Shared drawing primitives: theme, fonts, layout, number formatting, flags."""
from __future__ import annotations

import io
import os
import json
import logging
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

W, H, FPS = 1080, 1920, 30
FONTS = Path(__file__).resolve().parents[3] / "assets" / "fonts"
FALLBACK = Path("/usr/share/fonts/truetype/dejavu")

# Layout in production pixels. YouTube Shorts covers the bottom ~380px with the
# caption/channel bar and the right ~130px (from mid-height down) with buttons.
SAFE_TOP = 130
SAFE_BOTTOM = 1560
SAFE_LEFT = 48
SAFE_RIGHT = 1032
SAFE_RIGHT_LOW = 930  # right edge for content below y=900

# Categorical palette (validated 8-hue order) + 4 extra hues for 12-entity races.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948",
           "#0e7c86", "#8c5a2b", "#1f3a93", "#7a8a00"]


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    ink: str
    ink2: str
    muted: str
    grid: str
    card: str
    watermark: str


THEMES = {
    "Light": Theme("Light", "#fafaf7", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#ffffff", "#e3e2dc"),
    "Dark": Theme("Dark", "#12151c", "#f0efec", "#c3c2b7", "#8d8c86", "#262a33", "#1b1f28", "#232833"),
}


def rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a: str | tuple, b: str | tuple, t: float) -> tuple[int, int, int]:
    """Blend color a toward b by t (0 = a, 1 = b)."""
    a = rgb(a) if isinstance(a, str) else a
    b = rgb(b) if isinstance(b, str) else b
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


@lru_cache(maxsize=256)
def font(size: int, weight: str = "semibold") -> ImageFont.FreeTypeFont:
    files = {"medium": "Inter-Medium.ttf", "semibold": "Inter-SemiBold.ttf",
             "bold": "InterDisplay-Bold.ttf", "black": "InterDisplay-Black.ttf"}
    path = FONTS / files[weight]
    if not path.exists():
        path = FALLBACK / ("DejaVuSans-Bold.ttf" if weight in ("bold", "black") else "DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size)


def fit(d: ImageDraw.ImageDraw, text: str, width: int, size: int, weight="semibold", min_size=22) -> tuple[str, ImageFont.FreeTypeFont]:
    """Shrink text to fit width down to min_size, then ellipsize."""
    while size > min_size and d.textlength(text, font=font(size, weight)) > width:
        size -= 1
    f = font(size, weight)
    if d.textlength(text, font=f) <= width:
        return text, f
    while len(text) > 1 and d.textlength(text + "…", font=f) > width:
        text = text[:-1]
    return text.rstrip() + "…", f


def wrap(d: ImageDraw.ImageDraw, text: str, width: int, size: int, weight="black", max_lines=2, min_size=40) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """Wrap into <= max_lines, shrinking the font until it fits."""
    while True:
        f = font(size, weight)
        lines, line = [], ""
        for word in text.split():
            candidate = f"{line} {word}".strip()
            if d.textlength(candidate, font=f) <= width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
        if (len(lines) <= max_lines and all(d.textlength(l, font=f) <= width for l in lines)) or size <= min_size:
            return lines[:max_lines], f
        size -= 2


def ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ numbers
class Formatter:
    """Formats values consistently for one dataset (unit-aware, stable precision)."""

    def __init__(self, unit: str, values: list[float], integer: bool):
        u = (unit or "").strip()
        self.percent = u in {"%", "percent", "per cent"} or u.startswith("%")
        self.currency = "$" if re.search(r"\$|dollar|usd", u, re.I) else ("€" if "€" in u or "euro" in u.lower() else "")
        self.integer = integer
        self.peak = max(values) if values else 1

    def __call__(self, v: float, compact: bool = True) -> str:
        if self.percent:
            return f"{v:.1f}%" if v < 100 else f"{v:.0f}%"
        prefix = self.currency
        a = abs(v)
        if a == 0:
            return prefix + "0"
        if compact and a >= 1e6:
            for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
                if a >= div:
                    n = v / div
                    s = (f"{n:.0f}" if abs(n) >= 100 else f"{n:.1f}" if abs(n) >= 10 else f"{n:.2f}") + suffix
                    break
        elif self.integer or a >= 1000:
            s = f"{round(v):,}"
        elif a >= 100:
            s = f"{v:.0f}"
        elif a >= 10:
            s = f"{v:.1f}"
        else:
            s = f"{v:.2f}"
        return prefix + s


def nice_ticks(maximum: float, count: int = 4) -> list[float]:
    if maximum <= 0:
        return [0]
    raw = maximum / count
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=10 * mag)
    return [i * step for i in range(int(maximum / step) + 1)]


# -------------------------------------------------------------------- flags
def _circle_mask(size: int) -> Image.Image:
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    return big.resize((size, size), Image.Resampling.LANCZOS)


class Badges:
    """Round badges per entity: the national flag when available, else colored initials."""

    def __init__(self, entities, colors: dict[str, str], out: Path, theme: Theme):
        self.images: dict[str, Image.Image] = {}
        self.colors = colors
        self.theme = theme
        manifest = []
        session = None
        if not os.getenv("SHORTS_OFFLINE"):
            from ..sources.common import http
            session = http()
        for e in entities:
            if not e.iso2 or session is None:
                continue
            url = f"https://flagcdn.com/w320/{e.iso2.lower()}.png"
            try:
                r = session.get(url, timeout=(5, 15))
                r.raise_for_status()
                self.images[e.id] = Image.open(io.BytesIO(r.content)).convert("RGB")
                manifest.append({"entity": e.name, "url": url, "use": "flag badge"})
            except Exception as exc:
                log.info("No flag for %s: %s", e.name, exc)
        (out / "asset_sources.json").write_text(json.dumps(manifest, indent=2))
        self.names = {e.id: e.name for e in entities}

    @lru_cache(maxsize=512)
    def get(self, entity_id: str, size: int) -> tuple[Image.Image, Image.Image]:
        mask = _circle_mask(size)
        if entity_id in self.images:
            src = self.images[entity_id]
            side = min(src.size)
            crop = src.crop(((src.width - side) // 2, (src.height - side) // 2, (src.width + side) // 2, (src.height + side) // 2))
            img = crop.resize((size, size), Image.Resampling.LANCZOS)
        else:
            img = Image.new("RGB", (size, size), rgb(self.colors[entity_id]))
            d = ImageDraw.Draw(img)
            words = [w for w in re.findall(r"[A-Za-z0-9]+", self.names[entity_id]) if w.lower() not in {"fc", "cf", "the", "ac", "sc"}] or ["?"]
            initials = (words[0][0] + (words[1][0] if len(words) > 1 else "")).upper()
            f = font(int(size * 0.42), "bold")
            tw = d.textlength(initials, font=f)
            d.text(((size - tw) / 2, size * 0.27), initials, font=f, fill="white")
        ring = Image.new("RGB", (size, size), rgb(self.theme.card))
        ring.paste(img, (0, 0))
        return ring, mask

    def has_flag(self, entity_id: str) -> bool:
        return entity_id in self.images

    def paste(self, canvas: Image.Image, entity_id: str, x: float, y: float, size: int):
        img, mask = self.get(entity_id, size)
        canvas.paste(img, (int(x), int(y)), mask)


# ------------------------------------------------------------- medals & badges
MEDALS = {
    1: ("#ffe27a", "#f2b705", "#a87400", "#c8102e"),   # light, mid, dark, ribbon
    2: ("#f4f6f8", "#c3c9d1", "#7d8590", "#1f4e9c"),
    3: ("#f6c39a", "#cd7f32", "#7c4a1c", "#1b7f5a"),
}


@lru_cache(maxsize=64)
def medal(rank: int, size: int) -> Image.Image:
    """Gold / silver / bronze medal with ribbon, drawn at 4x and downsampled for smooth edges."""
    s = size * 4
    img = Image.new("RGBA", (s, int(s * 1.25)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    light, mid, dark, ribbon = MEDALS[rank]
    top = int(s * 0.25)
    # ribbon tails
    d.polygon([(s * .30, 0), (s * .48, 0), (s * .62, top + s * .2), (s * .44, top + s * .2)], fill=ribbon)
    d.polygon([(s * .70, 0), (s * .52, 0), (s * .38, top + s * .2), (s * .56, top + s * .2)], fill=mix(ribbon, "#000000", 0.25))
    # disc with a simple radial shading
    cx, cy, r = s / 2, top + s / 2, s / 2 - 2
    steps = 24
    for k in range(steps):
        t = k / (steps - 1)
        rr = r * (1 - t * 0.55)
        col = mix(dark, light, min(1, t * 1.4))
        off = r * 0.12 * t
        d.ellipse((cx - rr - off, cy - rr - off, cx + rr - off, cy + rr - off), fill=col)
    d.ellipse((cx - r * .74, cy - r * .74, cx + r * .74, cy + r * .74), outline=dark, width=max(2, s // 40))
    label = str(rank)
    f = font(int(s * 0.42), "black")
    tw = d.textlength(label, font=f)
    d.text((cx - tw / 2, cy - s * 0.27), label, font=f, fill=dark)
    return img.resize((size, int(size * 1.25)), Image.Resampling.LANCZOS)


@lru_cache(maxsize=64)
def rank_badge(rank: int, size: int, fill: str, ring: str, ink: str) -> Image.Image:
    """Uniform round rank badge (same size and font for every rank)."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, s - 1, s - 1), fill=ring)
    d.ellipse((s * .07, s * .07, s * .93, s * .93), fill=fill)
    label = str(rank)
    f = font(int(s * 0.44), "bold")
    tw = d.textlength(label, font=f)
    d.text(((s - tw) / 2, s * 0.21), label, font=f, fill=ink)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def paste(canvas: Image.Image, sprite: Image.Image, x: float, y: float):
    canvas.paste(sprite, (int(x), int(y)), sprite)


def ease_out_back(x: float) -> float:
    x = min(1.0, max(0.0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def uniform_font(d: ImageDraw.ImageDraw, labels: list[str], width: int, size: int, weight="semibold", min_size=26) -> ImageFont.FreeTypeFont:
    """One font size for a whole set of labels: the largest at which the longest fits (min_size floor)."""
    longest = max(labels, key=lambda l: d.textlength(l, font=font(size, weight)), default="")
    while size > min_size and d.textlength(longest, font=font(size, weight)) > width:
        size -= 1
    return font(size, weight)


def ellipsize(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> str:
    if d.textlength(text, font=f) <= width:
        return text
    while len(text) > 1 and d.textlength(text + "…", font=f) > width:
        text = text[:-1]
    return text.rstrip() + "…"
