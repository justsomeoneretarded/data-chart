"""Head-to-head layouts: two subjects over time, or two subjects across categories."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ..story import Interp, moments
from .base import Callout, Scene, Winner
from .kit import (SAFE_BOTTOM, ease_in_out, uniform_font, ellipsize, SAFE_LEFT, SAFE_RIGHT, SAFE_RIGHT_LOW, W, ease_out, fit, font, mix, nice_ticks)

CARD_GAP = 40


class Duel(Scene):
    """Two big cards with a live value each."""

    def setup_cards(self):
        self.a, self.b = [e.id for e in self.ds.entities[:2]]
        self.card_top = self.header_bottom + 92
        self.card_h = 340
        self.card_w = (SAFE_RIGHT - SAFE_LEFT - CARD_GAP) // 2

    def cards(self, im, d, values: dict[str, float], caption: str = "", appear: float = 1.0):
        th = self.theme
        leader = max((self.a, self.b), key=lambda e: values.get(e, 0))
        tied = math.isclose(values.get(self.a, 0), values.get(self.b, 0), rel_tol=1e-9)
        for i, eid in enumerate((self.a, self.b)):
            x = SAFE_LEFT + i * (self.card_w + CARD_GAP)
            y = self.card_top + (1 - appear) * 40
            color = self.colors[eid]
            d.rounded_rectangle((x, y, x + self.card_w, y + self.card_h), radius=28, fill=mix(th.bg, th.card, appear),
                                outline=mix(th.bg, color if eid == leader and not tied else th.grid, appear), width=4)
            badge = 112
            self.badges.paste(im, eid, x + (self.card_w - badge) / 2, y + 30, badge)
            f = uniform_font(d, [self.ds.name(self.a), self.ds.name(self.b)], self.card_w - 40, 40, "semibold", 26)
            name = ellipsize(d, self.ds.name(eid), f, self.card_w - 40)
            d.text((x + (self.card_w - d.textlength(name, font=f)) / 2, y + 158), name, font=f, fill=th.ink)
            vf = uniform_font(d, [self.fmt(values.get(self.a, 0)), self.fmt(values.get(self.b, 0))], self.card_w - 36, 78, "black", 34)
            value = self.fmt(values.get(eid, 0))
            d.text((x + (self.card_w - d.textlength(value, font=vf)) / 2, y + 222), value, font=vf, fill=th.ink)
            if eid == leader and not tied and appear > 0.9:
                chip = "AHEAD"
                cf = font(22, "bold")
                cw = d.textlength(chip, font=cf) + 30
                d.rounded_rectangle((x + self.card_w - cw - 18, y + 18, x + self.card_w - 18, y + 54), radius=18, fill=color)
                d.text((x + self.card_w - cw - 3, y + 24), chip, font=cf, fill="white")
            # color strip ties the card to its line / bars
            d.rounded_rectangle((x + 40, y + self.card_h - 18, x + self.card_w - 40, y + self.card_h - 10), radius=4, fill=mix(th.bg, color, appear))
        if caption:
            cap, cf = fit(d, caption, SAFE_RIGHT - SAFE_LEFT, 30, "medium", 22)
            d.text(((W - d.textlength(cap, font=cf)) / 2, self.card_top + self.card_h + 22), cap, font=cf, fill=th.ink2)
        return self.card_top + self.card_h + 70


class VersusTimeline(Duel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_cards()
        ds = self.ds
        self.interp = Interp(ds)
        self.y0, self.y1 = ds.years[0], ds.years[-1]
        values = ds.all_values()
        hi, lo = max(values), min(values)
        self.vmin = 0.0 if lo / hi < 0.45 else nice_ticks(lo * 0.92, 4)[-1] if lo > 0 else 0.0
        self.vmax = hi * 1.06
        self.chart = (128, self.card_top + self.card_h + 130, SAFE_RIGHT_LOW - 20, SAFE_BOTTOM - 60)
        for m in moments(ds):
            t = self.time_of(m.year)
            self.callouts.append(Callout(t, min(t + 2.8, self.duration - self.outro), f"{int(m.year)}: {m.text}", self.colors[m.entity_id]))
        final = self.interp.at(self.y1)
        if len(final) == 2:
            w = max(final, key=final.get)
            other = self.b if w == self.a else self.a
            ratio = final[w] / final[other] if final[other] else float("inf")
            gap = f"{ratio:.1f}× ahead" if ratio >= 1.5 else f"{(ratio - 1) * 100:.1f}% ahead" if ratio < 1.1 else f"{(ratio - 1) * 100:.0f}% ahead"
            self.winner = Winner(w, self.fmt(final[w]), f"{gap} in {self.y1}")

    def time_of(self, year: float) -> float:
        return self.intro + (year - self.y0) / max(1e-9, self.y1 - self.y0) * self.active

    def xy(self, year: float, value: float) -> tuple[float, float]:
        x0, y0, x1, y1 = self.chart
        x = x0 + (year - self.y0) / max(1e-9, self.y1 - self.y0) * (x1 - x0)
        y = y1 - (value - self.vmin) / max(1e-9, self.vmax - self.vmin) * (y1 - y0)
        return x, y

    def frame(self, t: float) -> Image.Image:
        im, d = self.canvas()
        th = self.theme
        x0, y0, x1, y1 = self.chart
        year = self.y0 + (self.y1 - self.y0) * self.progress(t)
        appear = ease_out(t / self.intro)
        label = str(int(year + 1e-6))
        wf = font(150, "black")
        d.text((x0 + 10, y0 - 10), label, font=wf, fill=th.watermark)
        self.header(im, d, t)
        values = self.interp.at(year)
        self.cards(im, d, values, appear=appear)
        # grid
        for tick in nice_ticks(self.vmax, 4):
            if tick < self.vmin:
                continue
            _, y = self.xy(self.y0, tick)
            if y < y0 - 5:
                continue
            d.line((x0, y, x1, y), fill=th.grid, width=2)
            lab = self.fmt(tick)
            lf = font(24, "medium")
            d.text((x0 - 16 - d.textlength(lab, font=lf), y - 14), lab, font=lf, fill=th.muted)
        for yr, anchor in ((self.y0, "l"), (self.y1, "r")):
            lab = str(yr)
            lf = font(26, "medium")
            x, _ = self.xy(yr, self.vmin)
            tx = x if anchor == "l" else x - d.textlength(lab, font=lf)
            d.text((tx, y1 + 16), lab, font=lf, fill=th.muted)
        # lines drawn progressively, with the gap shaded in the leader's color
        steps = max(2, int(240 * (year - self.y0) / max(1, self.y1 - self.y0)) + 2)
        samples = [self.y0 + (year - self.y0) * k / (steps - 1) for k in range(steps)]
        pts = {e: [] for e in (self.a, self.b)}
        for s in samples:
            v = self.interp.at(s)
            for e in pts:
                if e in v:
                    pts[e].append(self.xy(s, v[e]))
        if len(pts[self.a]) == len(pts[self.b]) == len(samples):
            for k in range(1, len(samples)):
                pa0, pa1, pb0, pb1 = pts[self.a][k - 1], pts[self.a][k], pts[self.b][k - 1], pts[self.b][k]
                lead = self.a if pa1[1] < pb1[1] else self.b
                d.polygon([pa0, pa1, pb1, pb0], fill=mix(th.bg, self.colors[lead], 0.16))
        for e, line in pts.items():
            if len(line) >= 2:
                d.line(line, fill=self.colors[e], width=7, joint="curve")
        for e, line in pts.items():
            if line:
                x, y = line[-1]
                d.ellipse((x - 13, y - 13, x + 13, y + 13), fill=th.card)
                d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=self.colors[e])
        self.callout(im, d, t, self.header_bottom + 10)
        return self.winner_banner(im, t)


class VersusCategories(Duel):
    """Category-by-category reveal (e.g. each trophy type), with running totals."""

    MAX_ROWS = 8

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_cards()
        cats = self.ds.categories
        if len(cats) > self.MAX_ROWS:
            cats = sorted(cats, key=lambda c: -sum(c.values.values()))[: self.MAX_ROWS]
        self.cats = cats
        self.slot = self.active / len(cats)
        self.top = self.card_top + self.card_h + 92
        self.pitch = min(150, (SAFE_BOTTOM - self.top) / len(cats))
        self.peak = max(v for c in cats for v in c.values.values()) or 1
        ta = sum(c.values[self.a] for c in cats)
        tb = sum(c.values[self.b] for c in cats)
        if ta != tb:
            w = self.a if ta > tb else self.b
            self.winner = Winner(w, f"{self.fmt(max(ta, tb))} – {self.fmt(min(ta, tb))}", f"across {len(cats)} categories")


    def frame(self, t: float) -> Image.Image:
        im, d = self.canvas()
        th = self.theme
        self.header(im, d, t)
        # Each category's bars grow across ~85% of its slot (no dead air between rows).
        progress = [ease_in_out((t - (self.intro + i * self.slot + self.slot * 0.15)) / (self.slot * 0.85)) for i in range(len(self.cats))]
        totals = {e: sum(c.values[e] * p for c, p in zip(self.cats, progress)) for e in (self.a, self.b)}
        shown = sum(p > 0 for p in progress)
        self.cards(im, d, totals, caption=f"Total across {shown} of {len(self.cats)} categories" if shown else "",
                   appear=ease_out(t / self.intro))
        center = W / 2
        half = 300
        for i, (cat, p) in enumerate(zip(self.cats, progress)):
            if p <= 0:
                continue
            y = self.top + i * self.pitch + (1 - p) * 20
            label, lf = fit(d, cat.label, 600, 30, "semibold", 22)
            d.text((center - d.textlength(label, font=lf) / 2, y), label, font=lf, fill=mix(th.bg, th.ink2, p))
            bar_y, bar_h = y + 46, int(min(54, self.pitch - 58))
            va, vb = cat.values[self.a], cat.values[self.b]
            for eid, v, side in ((self.a, va, -1), (self.b, vb, 1)):
                win = v >= (vb if eid == self.a else va)
                length = half * (v / self.peak) * p
                color = self.colors[eid] if win else mix(self.colors[eid], th.bg, 0.5)
                if length >= 2:
                    xa, xb = (center - 6 - length, center - 6) if side < 0 else (center + 6, center + 6 + length)
                    d.rounded_rectangle((xa, bar_y, xb, bar_y + bar_h), radius=min(8, int(length / 2)), fill=color)
                if p < 0.12:
                    continue  # values appear once the bars start moving
                vf = font(32, "bold")
                text = self.fmt(v * p if not self.ds.integer else round(v * p))
                tw = d.textlength(text, font=vf)
                tx = center - 6 - length - 14 - tw if side < 0 else center + 6 + length + 14
                d.text((tx, bar_y + bar_h / 2 - 20), text, font=vf, fill=th.ink if win else th.ink2)
        self.callout(im, d, t, self.header_bottom + 10)
        return self.winner_banner(im, t)
