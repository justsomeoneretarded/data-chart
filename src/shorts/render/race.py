"""Bar-chart race (timeseries) and countdown reveal (snapshot)."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ..story import Interp, moments
from .base import Callout, Scene
from .kit import (FPS, ease_in_out, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT_LOW, W, ease_out, fit, font, mix, nice_ticks)

NAME_RIGHT = 300   # names are right-aligned to this x
BAR_X = 322        # bars start here
BAR_MAX = 770      # right edge of the longest bar (values are drawn after it)


class Bars(Scene):
    """Layout shared by the race and the countdown."""

    def setup_rows(self, count: int):
        self.visible = min(10, count)
        self.chart_top = self.header_bottom + 150
        span = SAFE_BOTTOM - 20 - self.chart_top
        self.pitch = min(124, span / self.visible)
        self.bar_h = int(self.pitch * 0.70)

    def axis(self, d: ImageDraw.ImageDraw, scale: float):
        th = self.theme
        bottom = self.chart_top + self.visible * self.pitch
        for tick in nice_ticks(scale, 4):
            x = BAR_X + (BAR_MAX - BAR_X) * tick / scale
            if x > BAR_MAX + 1:
                continue
            d.line((x, self.chart_top - 14, x, bottom), fill=th.grid, width=2)
            label = self.fmt(tick)
            tw = d.textlength(label, font=font(24, "medium"))
            d.text((x - tw / 2, self.chart_top - 50), label, font=font(24, "medium"), fill=th.muted)

    def bar(self, im, d, eid: str, row: float, value: float, scale: float, dim: float = 0.0, rank_label: str = ""):
        th = self.theme
        y = self.chart_top + row * self.pitch + (self.pitch - self.bar_h) / 2
        color = mix(self.colors[eid], th.bg, dim)
        ink = mix(th.ink, th.bg, dim * 0.8)
        name, f = fit(d, self.ds.name(eid), NAME_RIGHT - SAFE_LEFT - (44 if rank_label else 0), 34, "semibold", 24)
        tw = d.textlength(name, font=f)
        d.text((NAME_RIGHT - tw, y + self.bar_h / 2 - f.size * 0.62), name, font=f, fill=ink)
        if rank_label:
            rf = font(26, "medium")
            d.text((SAFE_LEFT, y + self.bar_h / 2 - 16), rank_label, font=rf, fill=mix(th.muted, th.bg, dim))
        width = max(0.0, (BAR_MAX - BAR_X) * value / scale) if scale > 0 else 0
        if width >= 2:
            d.rounded_rectangle((BAR_X, y, BAR_X + width, y + self.bar_h), radius=min(10, int(width / 2)), fill=color)
        badge = int(self.bar_h * 0.82)
        vx = BAR_X + width + 14
        if self.badges.has_flag(eid):
            inside = width > badge + 14
            bx = BAR_X + width - badge - 7 if inside else BAR_X + width + 8
            if dim < 0.5:
                self.badges.paste(im, eid, bx, y + (self.bar_h - badge) / 2, badge)
            if not inside:
                vx = bx + badge + 12
        label = self.fmt(value)
        vf = font(34, "semibold")
        if vx + d.textlength(label, font=vf) > SAFE_RIGHT_LOW + 40:
            vf = font(28, "semibold")
        d.text((vx, y + self.bar_h / 2 - vf.size * 0.62), label, font=vf, fill=ink)


class Race(Bars):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ds = self.ds
        self.interp = Interp(ds)
        self.y0, self.y1 = ds.years[0], ds.years[-1]
        self.setup_rows(len(ds.entities))
        self.pos: dict[str, float] = {}
        self.scale = None
        for m in moments(ds):
            t = self.time_of(m.year)
            self.callouts.append(Callout(t, min(t + 2.8, self.duration - self.outro), m.text, self.colors[m.entity_id]))
        final = self.interp.at(self.y1)
        winner = max(final, key=final.get)
        self.callouts.append(Callout(self.duration - self.outro + 0.2, self.duration,
                                     f"#1 in {self.y1}: {ds.name(winner)} · {self.fmt(final[winner])}", self.colors[winner]))

    def rank(self, values: dict[str, float]) -> list[str]:
        """Stable ranking with hysteresis so near-ties don't flicker back and forth."""
        order = [e for e in getattr(self, "_order", []) if e in values]
        order += sorted((e for e in values if e not in order), key=lambda e: -values[e])
        # Swap only when the gap is visible on the axis (~1% of its width).
        margin = 0.01 * (self.scale or max(values.values()))
        changed = True
        while changed:
            changed = False
            for i in range(len(order) - 1):
                a, b = order[i], order[i + 1]
                if values[b] - values[a] > margin:
                    order[i], order[i + 1] = b, a
                    changed = True
        self._order = order
        return order

    def subtitle(self) -> str:
        span = f"{self.ds.years[0]}–{self.ds.years[-1]}"
        return f"{self.ds.unit}  ·  {span}" if self.ds.unit else span

    def time_of(self, year: float) -> float:
        return self.intro + (year - self.y0) / max(1e-9, self.y1 - self.y0) * self.active

    def frame(self, t: float) -> Image.Image:
        im, d = self.canvas()
        th = self.theme
        year = self.y0 + (self.y1 - self.y0) * self.progress(t)
        values = self.interp.at(year)
        grow = ease_out(t / self.intro)
        ranked = self.rank(values)
        # Smoothly follow rank targets: swaps glide instead of jumping.
        follow = 1 - (1 - 0.28) ** (30 / FPS)
        for i, eid in enumerate(ranked):
            target = min(i, self.visible + 0.6)
            current = self.pos.get(eid, self.visible + 0.6)
            self.pos[eid] = current + (target - current) * follow
        for eid in list(self.pos):
            if eid not in values:
                self.pos[eid] += (self.visible + 1 - self.pos[eid]) * follow
        # Smooth axis scale: grows quickly, shrinks gently.
        top = max((values[e] for e in ranked[: self.visible]), default=1) * 1.04
        if self.scale is None:
            self.scale = top
        rate = 0.25 if top > self.scale else 0.06
        self.scale += (top - self.scale) * rate

        # watermark year behind the bars
        label = str(int(year + 1e-6))
        wf = font(210, "black")
        tw = d.textlength(label, font=wf)
        d.text((SAFE_RIGHT_LOW - tw, SAFE_BOTTOM - 250), label, font=wf, fill=th.watermark)

        self.header(im, d, t)
        self.axis(d, self.scale)
        ending = max(0.0, min(1.0, (t - (self.duration - self.outro)) / 0.6))
        order = sorted(self.pos, key=lambda e: -self.pos[e])  # draw lower rows first
        for eid in order:
            row = self.pos[eid]
            if row > self.visible - 0.05 or eid not in values:
                continue
            rank = ranked.index(eid)
            dim = 0.62 * ending if rank >= 3 else 0.0
            self.bar(im, d, eid, row, values[eid] * grow, self.scale, dim)
        self.callout(im, d, t, self.header_bottom + 8)
        return im


class Countdown(Bars):
    """Snapshot data: reveal from the last place up to #1."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        snap = self.ds.snapshot
        self.order = sorted(snap, key=lambda e: -snap[e])[:10]
        self.setup_rows(len(self.order))
        self.scale = snap[self.order[0]] * 1.04
        n = len(self.order)
        self.slot = self.active / n
        first = self.order[0]
        start = self.intro + self.active
        self.callouts.append(Callout(start, self.duration, f"#1: {self.ds.name(first)} · {self.fmt(snap[first])}", self.colors[first]))

    def subtitle(self) -> str:
        parts = [p for p in [self.ds.unit, self.ds.as_of] if p]
        return "  ·  ".join(parts)

    def frame(self, t: float) -> Image.Image:
        im, d = self.canvas()
        th = self.theme
        self.header(im, d, t)
        self.axis(d, self.scale)
        n = len(self.order)
        # Each bar grows and counts up across ~85% of its slot, so the screen keeps
        # moving; #1 finishes exactly as the final hold begins.
        reveal = self.slot * 0.85
        latest = None
        for i, eid in enumerate(self.order):
            reveal_at = self.intro + (n - 1 - i) * self.slot + self.slot * 0.15
            p = ease_in_out((t - reveal_at) / reveal)
            if p <= 0:
                continue
            latest = i
            value = self.ds.snapshot[eid] * p
            row = i + (1 - p) * 0.35
            self.bar(im, d, eid, row, value, self.scale, rank_label=f"{i + 1}")
        if latest is not None:
            # A soft pulsing marker on the newest bar keeps the screen alive between reveals.
            eid = self.order[latest]
            y = self.chart_top + latest * self.pitch + self.pitch / 2
            pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 1.6)
            r = 5 + 3 * pulse
            x = (NAME_RIGHT + BAR_X) / 2
            color = mix(th.bg, self.colors[eid], 0.35 + 0.65 * pulse)
            d.ellipse((x - r, y - r, x + r, y + r), fill=color)
        self.callout(im, d, t, self.header_bottom + 8)
        return im
