"""Bar-chart race (timeseries) and countdown reveal (snapshot).

Layout per row: rank badge (medal for 1-3) | name above a full-width bar | value at the bar's end.
Every name uses the same font size, and every rank badge the same size and font.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ..story import Interp, moments
from .base import Callout, Scene, Winner
from .kit import (FPS, SAFE_BOTTOM, SAFE_LEFT, W, ease_in_out, ease_out, ease_out_back, ellipsize, font,
                  medal, mix, paste, rank_badge, rgb, uniform_font)

BADGE = 66            # rank badge diameter
BAR_X = 140           # names and bars start here
BAR_MAX = 952         # right edge of the longest bar (clear of the Shorts side buttons)
FLAG = 40


def _light(hex_color: str) -> bool:
    r, g, b = rgb(hex_color)
    return 0.299 * r + 0.587 * g + 0.114 * b > 150


class Bars(Scene):
    """Shared row layout for the race and the countdown."""

    def setup_rows(self, count: int, names: list[str]):
        self.visible = min(10, count)
        self.chart_top = self.header_bottom + 100          # room for the callout pill
        span = SAFE_BOTTOM - self.chart_top
        self.pitch = min(132, span / self.visible)
        d = ImageDraw.Draw(Image.new("RGB", (W, 10)))
        size = max(30, min(44, int(self.pitch * 0.36)))
        self.name_font = uniform_font(d, names, BAR_MAX - BAR_X - FLAG - 10, size, "semibold", min_size=26)
        self.value_font = font(max(30, min(40, int(self.pitch * 0.33))), "bold")
        self.name_h = int(self.name_font.size * 1.22)
        self.bar_h = int(max(30, self.pitch - self.name_h - 14))

    def slot_y(self, row: float) -> float:
        return self.chart_top + row * self.pitch

    def badge(self, im, rank: int, row: float, dim: float = 0.0, as_medal: bool = True, pop: float = 1.0):
        th = self.theme
        cy = self.slot_y(row) + self.name_h / 2 + self.bar_h / 2 + 4
        if rank <= 3 and as_medal:
            size = int(BADGE * 1.18 * (0.6 + 0.4 * pop))
            m = medal(rank, size)
            paste(im, m, SAFE_LEFT + (BADGE - size) / 2, cy - m.height * 0.62)
        else:
            fill = mix(th.card, th.bg, dim)
            ring = mix(th.grid, th.bg, dim)
            ink = mix(th.ink2, th.bg, dim)
            paste(im, rank_badge(rank, BADGE, _hex(fill), _hex(ring), _hex(ink)), SAFE_LEFT, cy - BADGE / 2)

    def row(self, im, d, eid: str, row: float, value: float, scale: float, dim: float = 0.0,
            name_reveal: float = 1.0):
        th = self.theme
        y = self.slot_y(row)
        x = BAR_X
        color = mix(self.colors[eid], th.bg, dim)
        if self.badges.has_flag(eid) and name_reveal > 0.5:
            self.badges.paste(im, eid, x, y + (self.name_h - FLAG) / 2, FLAG)
            x += FLAG + 12
        if name_reveal < 1.0:
            hidden = "?  ?  ?"
            d.text((x, y), hidden, font=self.name_font, fill=mix(th.muted, th.bg, name_reveal))
        if name_reveal > 0:
            name = ellipsize(d, self.ds.name(eid), self.name_font, BAR_MAX - x)
            d.text((x, y), name, font=self.name_font, fill=mix(th.bg, mix(th.ink, th.bg, dim * 0.8), name_reveal))
        by = y + self.name_h
        width = max(0.0, (BAR_MAX - BAR_X) * value / scale) if scale > 0 else 0
        if width >= 2:
            d.rounded_rectangle((BAR_X, by, BAR_X + width, by + self.bar_h), radius=min(self.bar_h // 2, 14, int(width / 2)), fill=color)
        if value <= 0:
            return
        label = self.fmt(value)
        vf = self.value_font
        tw = d.textlength(label, font=vf)
        ty = by + self.bar_h / 2 - vf.size * 0.62
        if width > tw + 44:
            ink = "#111111" if _light(self.colors[eid]) else "#ffffff"
            d.text((BAR_X + width - tw - 20, ty), label, font=vf, fill=mix(ink, th.bg, dim))
        else:
            d.text((BAR_X + width + 14, ty), label, font=vf, fill=mix(th.ink, th.bg, dim * 0.8))


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(c)


class Race(Bars):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ds = self.ds
        self.interp = Interp(ds)
        self.y0, self.y1 = ds.years[0], ds.years[-1]
        self.setup_rows(len(ds.entities), [e.name for e in ds.entities])
        self.pos: dict[str, float] = {}
        self.scale = None
        for m in moments(ds):
            t = self.time_of(m.year)
            self.callouts.append(Callout(t, min(t + 2.8, self.duration - self.outro), m.text, self.colors[m.entity_id]))
        final = self.interp.at(self.y1)
        win = max(final, key=final.get)
        self.winner = Winner(win, self.fmt(final[win]), f"#1 in {self.y1}")

    def rank(self, values: dict[str, float]) -> list[str]:
        """Stable ranking with hysteresis so near-ties don't flicker back and forth."""
        order = [e for e in getattr(self, "_order", []) if e in values]
        order += sorted((e for e in values if e not in order), key=lambda e: -values[e])
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

    def time_of(self, year: float) -> float:
        return self.intro + (year - self.y0) / max(1e-9, self.y1 - self.y0) * self.active

    def frame(self, t: float) -> Image.Image:
        im, d = self.canvas()
        th = self.theme
        year = self.y0 + (self.y1 - self.y0) * self.progress(t)
        values = self.interp.at(year)
        grow = ease_out(t / self.intro)
        ranked = self.rank(values)
        follow = 1 - (1 - 0.28) ** (30 / FPS)
        for i, eid in enumerate(ranked):
            target = min(i, self.visible + 0.6)
            current = self.pos.get(eid, self.visible + 0.6)
            self.pos[eid] = current + (target - current) * follow
        for eid in list(self.pos):
            if eid not in values:
                self.pos[eid] += (self.visible + 1 - self.pos[eid]) * follow
        top = max((values[e] for e in ranked[: self.visible]), default=1) * 1.02
        if self.scale is None:
            self.scale = top
        rate = 0.25 if top > self.scale else 0.06
        self.scale += (top - self.scale) * rate

        # big year, bottom right, behind the bars
        label = str(int(year + 1e-6))
        wf = font(230, "black")
        d.text((BAR_MAX - d.textlength(label, font=wf), SAFE_BOTTOM - 250), label, font=wf, fill=th.watermark)

        self.header(im, d, t)
        for slot in range(self.visible):       # rank numbers stay put; bars move between them
            self.badge(im, slot + 1, slot)
        for eid in sorted(self.pos, key=lambda e: -self.pos[e]):
            row = self.pos[eid]
            if eid not in values:
                continue
            # rows sliding out of the top 10 fade away instead of spilling below the chart
            fade = min(1.0, max(0.0, (row - (self.visible - 1)) / 0.7))
            if fade >= 0.98:
                continue
            self.row(im, d, eid, row, values[eid] * grow, self.scale, dim=fade)
        self.callout(im, d, t, self.header_bottom + 10)
        return self.winner_banner(im, t)


class Countdown(Bars):
    """Snapshot data: reveal from last place up to #1. Names stay hidden until their bar lands."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        snap = self.ds.snapshot
        self.order = sorted(snap, key=lambda e: -snap[e])[:10]
        self.setup_rows(len(self.order), [self.ds.name(e) for e in self.order])
        self.scale = snap[self.order[0]] * 1.02
        self.slot = self.active / len(self.order)
        first = self.order[0]
        self.winner = Winner(first, self.fmt(snap[first]), self.ds.as_of)

    def subtitle(self) -> str:
        base = super().subtitle()
        return base

    def frame(self, t: float) -> Image.Image:
        im, d = self.canvas()
        th = self.theme
        self.header(im, d, t)
        n = len(self.order)
        for i, eid in enumerate(self.order):
            start = self.intro + (n - 1 - i) * self.slot
            local = (t - start) / self.slot          # 0..1 across this item's slot
            y = self.slot_y(i)
            if local < 0:
                # not revealed yet: numbered placeholder + empty track builds anticipation
                appear = ease_out(t / self.intro)
                self.badge(im, i + 1, i, dim=0.45 + 0.55 * (1 - appear), as_medal=False)
                by = y + self.name_h
                d.rounded_rectangle((BAR_X, by, BAR_MAX, by + self.bar_h), radius=min(self.bar_h // 2, 14),
                                    fill=mix(th.bg, th.grid, 0.55 * appear))
                d.text((BAR_X, y), "?", font=self.name_font, fill=mix(th.bg, th.muted, appear))
                continue
            active = local < 1.0
            if active:
                # highlight the row being revealed
                glow = 0.10 + 0.05 * math.sin(t * 2 * math.pi / 1.2)
                d.rounded_rectangle((SAFE_LEFT - 18, y - 10, BAR_MAX + 40, y + self.pitch - 4), radius=20,
                                    fill=mix(th.bg, self.colors[eid], glow))
            grow = ease_in_out((local - 0.12) / 0.62)
            reveal = ease_out((local - 0.62) / 0.18)
            self.badge(im, i + 1, i, as_medal=True, pop=ease_out_back(reveal) if i < 3 else 1.0)
            self.row(im, d, eid, i, self.ds.snapshot[eid] * grow, self.scale, name_reveal=reveal)
        self.callout(im, d, t, self.header_bottom + 10)
        return self.winner_banner(im, t)
