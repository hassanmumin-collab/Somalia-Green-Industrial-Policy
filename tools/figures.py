#!/usr/bin/env python3
"""Generate the report's figures from the registers and the model (CLAUDE.md section 12A).

Every number drawn comes from data/claims.yaml (through C()) or from the model's base scenario (through M()), so a figure
cannot drift from the registers. Each figure is recorded in data/figures.yaml with the claim IDs and model output keys
it uses, its source line and its file. The verifier checks that registry (check 23).

House style (Hassan Mumin, 2026-09-25): all text in Times New Roman at 11 point. Every figure passes a layout audit
before it is saved: no text may overlap other text, run partly off a bar or box, sit in white on an unfilled area, or
lack contrast with the shape behind it. A figure that fails the audit is not written.

Usage: python tools/figures.py            (all figures)
       python tools/figures.py 1.1 1.4     (selected figures)
"""
from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Polygon, Rectangle  # noqa: E402
from matplotlib.text import Text  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from model import engine  # noqa: E402

OUT = ROOT / "report" / "figures"
REGISTRY = ROOT / "data" / "figures.yaml"

FS = 11  # allow-literal: every text element in every figure is 11 point (Hassan Mumin, 2026-09-25)
FONT = "Times New Roman"
NAVY, BLUE, LIGHT, GREY, ORANGE, GREEN, RED = "#0B3C5D", "#328CC1", "#A9CCE3", "#7F7F7F", "#C0691E", "#2E6B37", "#A93226"
PALE_GREY = "#D5D8DC"
plt.rcParams.update({
    "font.family": "serif", "font.serif": [FONT], "mathtext.fontset": "custom", "mathtext.rm": FONT,
    "font.size": FS, "axes.titlesize": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS,
    "legend.fontsize": FS, "figure.titlesize": FS, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GREY, "axes.grid": True,
    "grid.color": "#E5E5E5", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
    "figure.dpi": 100, "savefig.dpi": 220, "savefig.bbox": "tight", "savefig.pad_inches": 0.08})
WIDTH = 6.5  # inches, the text width of the Word template


def wrap(s: str, width: int) -> str:
    return "\n".join(textwrap.wrap(s, width, break_on_hyphens=False))


# --------------------------------------------------------------------------- context

class Ctx:
    """Tracks every claim and model output a figure uses."""

    def __init__(self):
        self.claims = {c["id"]: c for c in yaml.safe_load((ROOT / "data" / "claims.yaml").read_text(encoding="utf-8"))}
        self.sources = {s["id"]: s for s in yaml.safe_load((ROOT / "data" / "sources.yaml").read_text(encoding="utf-8"))}
        self.model = engine.compute("base", ROOT)
        self.reset()

    def reset(self):
        self.used_c, self.used_m, self.used_s = [], [], []

    def C(self, cid):
        c = self.claims[cid]
        if cid not in self.used_c:
            self.used_c.append(cid)
        try:
            return engine._num(str(c["value"]).replace(",", ""))
        except ValueError:
            return c["value"]  # qualitative claim (for example a list of regions)

    def sources_of(self, cid, seen=None):
        """Source IDs behind a claim, following derived-claim formulas back to their inputs."""
        seen = seen or set()
        if cid in seen:
            return set()
        seen.add(cid)
        c = self.claims[cid]
        if c.get("source_id"):
            return {c["source_id"]}
        refs = re.findall(r"[CD]-\d{4}", str(c.get("formula", "")))
        return set().union(*[self.sources_of(r, seen) for r in refs]) if refs else set()

    def M(self, key):
        if key not in self.used_m:
            self.used_m.append(key)
        return self.model[key]["value"]

    def S(self, sid):
        """A geospatial or reference source used directly (maps)."""
        if sid not in self.used_s:
            self.used_s.append(sid)
        return ROOT / self.sources[sid]["local_path"]


FIGURES = {}


def figure(fid, title, source, note=""):
    def deco(fn):
        FIGURES[fid] = dict(fn=fn, title=title, source=source, note=note)
        return fn
    return deco


# --------------------------------------------------------------------------- layout audit

def _luminance(c):
    r, g, b = to_rgb(c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def audit(fig) -> list:
    """Return layout problems: overlapping text, text partly off a bar or box, white text off a filled shape,
    low-contrast text, and any text not in the house font and size."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    texts = [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
    boxes = [(t, t.get_window_extent(rend).expanded(1.0, 1.0)) for t in texts]
    problems = []
    for t in texts:
        if abs(t.get_fontsize() - FS) > 0.01:
            problems.append(f"'{t.get_text()[:30]}' is {t.get_fontsize():g} pt, not {FS} pt")
        fam = t.get_fontname()
        if fam != FONT:
            problems.append(f"'{t.get_text()[:30]}' is in {fam}, not {FONT}")
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ti, bi), (tj, bj) = boxes[i], boxes[j]
            w = min(bi.x1, bj.x1) - max(bi.x0, bj.x0)
            h = min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
            if w > 1.5 and h > 1.5:
                problems.append(f"text overlaps: '{ti.get_text()[:30]}' and '{tj.get_text()[:30]}'")
    shapes = []
    for ax in fig.axes:
        ab = ax.get_window_extent(rend)
        for p in ax.patches:
            if isinstance(p, (Rectangle, FancyBboxPatch)) and p.get_fill() and p.get_visible():
                pb = p.get_window_extent(rend)
                if p.get_clip_on():  # only the part inside the plotting area is visible
                    pb = type(pb).from_extents(max(pb.x0, ab.x0), max(pb.y0, ab.y0), min(pb.x1, ab.x1), min(pb.y1, ab.y1))
                if pb.width > 0 and pb.height > 0:
                    shapes.append((p, pb))
    import numpy as np
    for ax in fig.axes:  # text must not sit on a plotted line (rivers, reference lines)
        for ln in ax.lines:
            xy = ln.get_xydata()
            if len(xy) < 2 or not ln.get_visible() or ln.get_linestyle() in ("None", ""):
                continue
            pts = ln.get_transform().transform(xy)
            dense = np.concatenate([np.linspace(pts[k], pts[k + 1], 12) for k in range(len(pts) - 1)])
            for t, _ in boxes:
                tb = t.get_window_extent(rend)
                hit = ((dense[:, 0] > tb.x0 + 1) & (dense[:, 0] < tb.x1 - 1)
                       & (dense[:, 1] > tb.y0 + 1) & (dense[:, 1] < tb.y1 - 1))
                if hit.any():
                    problems.append(f"text sits on a plotted line: '{t.get_text()[:30]}'")
    for t, b in boxes:
        tb = t.get_window_extent(rend)
        inside, partial = None, False
        for p, pb in shapes:
            w = min(tb.x1, pb.x1) - max(tb.x0, pb.x0)
            h = min(tb.y1, pb.y1) - max(tb.y0, pb.y0)
            if w <= 1 or h <= 1:
                continue
            if tb.x0 >= pb.x0 - 1 and tb.x1 <= pb.x1 + 1 and tb.y0 >= pb.y0 - 1 and tb.y1 <= pb.y1 + 1:
                inside = p
            else:
                partial = True
        if partial and inside is None:
            problems.append(f"text runs partly off a bar or box: '{t.get_text()[:30]}'")
        if _luminance(t.get_color()) > 0.9 and inside is None:
            problems.append(f"white text is not fully on a filled shape: '{t.get_text()[:30]}'")
        if inside is not None and abs(_luminance(t.get_color()) - _luminance(inside.get_facecolor())) < 0.45:
            problems.append(f"low contrast between text and its box: '{t.get_text()[:30]}'")
    return problems


def save(fig, fid):
    problems = audit(fig)
    if problems:
        plt.close(fig)
        raise SystemExit(f"Figure {fid} failed the layout audit:\n  " + "\n  ".join(dict.fromkeys(problems)))
    import os
    import time
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"fig_{fid.replace('.', '_')}.png"
    tmp = path.with_suffix(".tmp.png")
    fig.savefig(tmp)
    plt.close(fig)
    for attempt in range(10):  # OneDrive can hold a brief lock on the old file while it syncs
        try:
            os.replace(tmp, path)
            break
        except OSError:
            time.sleep(1)
    else:
        raise SystemExit(f"could not replace {path}; close any program that has it open")
    return path


def hbar_labels(ax, values, fmt, pad):
    """Value labels just beyond the end of horizontal bars."""
    for i, v in enumerate(values):
        ax.text(v + pad, i, fmt(v), va="center")


# --------------------------------------------------------------------------- Part 1

@figure("1.1", "Electricity costs: Somalia against the region and against solar power in the parks",
        "World Bank, Somalia Economic Update 11 (2026), Table 4; Ministry of Energy generation plan (2025); "
        "model base scenario (modelled estimate).",
        "Average tariffs; the source table does not state the year. Pale bars show the top of a range where the source "
        "gives one. Park solar and storage is the model's levelised cost for the park supply in the base scenario "
        "(illustrative, not a forecast).")
def fig_1_1(x: Ctx):
    rows = [("Ethiopia", x.C("C-0487"), x.C("C-0488")), ("Sudan", x.C("C-0491"), None),
            ("Eritrea", x.C("C-0486"), None), ("Kenya", x.C("C-0489"), None), ("Djibouti", x.C("C-0485"), None),
            ("South Sudan", x.C("C-0490"), None), ("Somalia", x.C("C-0083"), x.C("C-0084"))]
    solar = x.M("climate.minigrid.lcoe_usd_per_kwh") * 100
    diesel = x.C("D-0079")
    fig, ax = plt.subplots(figsize=(WIDTH, 4.2))
    for i, (name, lo, hi) in enumerate(rows):
        col = RED if name == "Somalia" else BLUE
        if hi is None:
            ax.barh(i, lo, color=col, height=0.6)
            ax.text(lo + 1.2, i, f"{lo:g}", va="center")
        else:
            ax.barh(i, hi, color=col, height=0.6, alpha=0.35)
            ax.barh(i, lo, color=col, height=0.6)
            ax.text(max(hi, solar) + 1.5, i, f"{lo:g} to {hi:g}", va="center")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.axvline(solar, color=GREEN, lw=1.8, ls="--", label=f"Park solar and storage (model, base): {solar:.1f}")
    ax.axvline(diesel, color=ORANGE, lw=1.6, ls=":", label=f"Diesel self-generation: {diesel:g}")
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=1)
    ax.set_xlabel("US cents per kWh")
    ax.set_xlim(0, 105)
    ax.grid(axis="y", visible=False)
    return fig


@figure("1.2", "An import-dependent economy",
        "Somalia National Bureau of Statistics, GDP 2025 release (2026) and Quarterly Statistical Bulletins 2024.",
        "Panel B shows the import categories the NBS bulletins report separately; they do not sum to total imports.")
def fig_1_2(x: Ctx):
    fig, (a, b) = plt.subplots(2, 1, figsize=(WIDTH, 5.6), gridspec_kw=dict(height_ratios=[1, 1.35], hspace=0.55))
    items = [("GDP", x.C("C-0001"), GREY), ("Imports of goods and services", x.C("C-0014"), RED),
             ("Exports of goods and services", x.C("C-0011"), BLUE)]
    a.barh(range(3), [v for _, v, _ in items], color=[c for *_, c in items], height=0.6)
    a.invert_yaxis()
    a.set_yticks(range(3), [n for n, *_ in items])
    hbar_labels(a, [v for _, v, _ in items], lambda v: f"{v:,.0f}", 200)
    a.set_xlim(0, max(v for _, v, _ in items) * 1.18)
    a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a.set_title("A. The economy in 2025 (USD million, current prices)")
    a.grid(axis="y", visible=False)
    cats = [("Food", "D-0002"), ("Clothes and footwear", "D-0003"), ("Oil and gas", "D-0001"),
            ("Personal care", "D-0005"), ("Cosmetics", "D-0004")]
    v2 = [x.C(c) for _, c in cats]
    b.barh(range(len(cats)), v2, color=NAVY, height=0.6)
    b.invert_yaxis()
    b.set_yticks(range(len(cats)), [n for n, _ in cats])
    hbar_labels(b, v2, lambda v: f"{v:,.1f}", 40)
    b.set_xlim(0, max(v2) * 1.22)
    b.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    b.set_title("B. Selected imports, 2024 (USD million)")
    b.grid(axis="y", visible=False)
    return fig


@figure("1.3", "Value left on the table: raw exports against processed products",
        "UN Comtrade (importer-reported CIF unit values, 2023), compiled for this policy.",
        "Panel A: live cattle are valued per kg of live weight, chilled beef per kg of meat, so the ladder shows prices "
        "per kilogram of product, not margins. Panel B uses a logarithmic scale; HS 1301 also covers gums other than "
        "frankincense and myrrh.")
def fig_1_3(x: Ctx):
    fig, (a, b) = plt.subplots(2, 1, figsize=(WIDTH, 6.0), gridspec_kw=dict(hspace=0.5))
    beef = [("Live cattle, Somalia to Oman", x.C("D-0056"), GREY), ("Chilled beef, Pakistan to GCC", x.C("D-0066"), BLUE),
            ("Chilled beef, GCC average", x.C("D-0054"), BLUE), ("Chilled beef, Ethiopia to Saudi Arabia", x.C("D-0067"), NAVY)]
    a.barh(range(4), [v for _, v, _ in beef], color=[c for *_, c in beef], height=0.6)
    a.invert_yaxis()
    a.set_yticks(range(4), [n for n, *_ in beef])
    hbar_labels(a, [v for _, v, _ in beef], lambda v: f"{v:.2f}", 0.15)
    a.set_xlim(0, 11.5)
    a.set_title("A. Cattle and beef (USD per kg)")
    a.grid(axis="y", visible=False)
    resin = [("Resin to the UAE", x.C("D-0076"), GREY), ("Resin to China", x.C("D-0077"), GREY),
             ("Resin to France and Germany", x.C("D-0068"), BLUE), ("Essential oils, all buyers", x.C("D-0069"), NAVY)]
    b.barh(range(4), [v for _, v, _ in resin], color=[c for *_, c in resin], height=0.6)
    b.invert_yaxis()
    b.set_xscale("log")
    b.set_yticks(range(4), [n for n, *_ in resin])
    for i, (_, v, _) in enumerate(resin):
        b.text(v * 1.12, i, f"{v:,.2f}" if v < 100 else f"{v:,.0f}", va="center")
    b.set_xlim(1, 900)
    b.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    b.set_title("B. Somali gums, resins and oils (USD per kg, log scale)")
    b.grid(axis="y", visible=False)
    return fig


@figure("1.4", "Who supplies the Gulf's chilled beef, 2023",
        "UN Comtrade, imports of fresh or chilled bovine meat (HS 0201) reported by the six GCC states, 2023.",
        "Shares of the USD 1,094.9 million the six GCC states imported, by value.")
def fig_1_4(x: Ctx):
    parts = [("Pakistan", x.C("D-0064"), NAVY), ("Australia", x.C("D-0073"), BLUE), ("Brazil", x.C("D-0074"), BLUE),
             ("India", x.C("D-0075"), BLUE), ("All other suppliers", x.C("D-0078"), GREY)]
    x.C("D-0053")
    fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
    vals = [v * 100 for _, v, _ in parts]
    ax.barh(range(len(parts)), vals, color=[c for *_, c in parts], height=0.6)
    ax.invert_yaxis()
    ax.set_yticks(range(len(parts)), [n for n, *_ in parts])
    hbar_labels(ax, vals, lambda v: f"{v:.1f}%", 0.6)
    ax.set_xlim(0, 43)
    ax.set_xlabel("Percent of GCC imports by value")
    ax.grid(axis="y", visible=False)
    return fig


@figure("1.5", "The cost of climate shocks",
        "Somalia R-PDNA for the 2023 Deyr floods (SoDMA with the UN, World Bank and EU, 2024); World Bank, Somalia "
        "Infrastructure Development for Access and Jobs project appraisal (2026), citing an ongoing Mogadishu flood risk assessment.",
        "Panel A covers the sixteen districts assessed. Panel B: average annual losses are an expected value across flood "
        "years; the same assessment finds that 61 percent of households report income losses from floods.")
def fig_1_5(x: Ctx):
    fig, (a, b) = plt.subplots(2, 1, figsize=(WIDTH, 4.6), gridspec_kw=dict(height_ratios=[1.6, 1], hspace=0.7))
    dmg, loss, tot, trans = x.C("C-0527"), x.C("C-0528"), x.C("C-0499"), x.C("C-0500")
    rows = [("Damages", dmg, NAVY), ("Losses", loss, BLUE), ("Total effects", tot, GREY), ("of which transport", trans, LIGHT)]
    a.barh(range(4), [v for _, v, _ in rows], color=[c for *_, c in rows], height=0.6)
    a.invert_yaxis()
    a.set_yticks(range(4), [n for n, *_ in rows])
    hbar_labels(a, [v for _, v, _ in rows], lambda v: f"{v:.1f}", 2)
    a.set_xlim(0, tot * 1.2)
    a.set_title("A. 2023 Deyr floods, sixteen districts (USD million)")
    a.grid(axis="y", visible=False)
    aal, share = x.C("C-0493"), x.C("C-0494")
    b.barh([0], [aal], color=RED, height=0.5)
    b.set_yticks([0], ["Mogadishu"])
    hbar_labels(b, [aal], lambda v: f"{v:g} a year", 2)
    b.set_xlim(0, tot * 1.2)
    b.set_ylim(-0.6, 0.6)
    b.set_title("B. Average annual flood losses (USD million)")
    b.grid(axis="y", visible=False)
    return fig


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


@figure("1.6", "Somalia's productive geography and the park-to-port system",
        "Boundaries: geoBoundaries (OpenStreetMap). Rivers and towns: Natural Earth. Resin regions: National Export "
        "Strategy. Policy design: this policy.",
        "Boundaries shown are not an endorsement of any boundary or delimitation. The industrial park location is "
        "indicative (outskirts of Mogadishu); sites will be fixed during the preparatory period.")
def fig_1_6(x: Ctx):
    adm = _load(x.S("S-159"))
    rivers = _load(x.S("S-160"))
    places = _load(x.S("S-161"))
    countries = _load(x.S("S-162"))
    x.C("C-0525")
    x.C("C-0526")
    fig, ax = plt.subplots(figsize=(WIDTH, 7.6))
    for f in countries["features"]:
        if f["properties"].get("ADMIN", "") in ("Ethiopia", "Kenya", "Djibouti", "Yemen"):
            for ring in _rings(f["geometry"]):
                ax.add_patch(Polygon(ring, closed=True, fc="#F2F2F2", ec="#BFBFBF", lw=0.5))
    resin = {"Sanaag", "Bari"}
    riverine = {"Middle Shebelle", "Lower Shebelle", "Middle Juba", "Lower Juba", "Hiiraan", "Gedo"}
    for f in adm["features"]:
        nm = f["properties"]["shapeName"]
        fc = "#F3E3C3" if nm in resin else "#DCEFD9" if nm in riverine else "#FFFFFF"
        for ring in _rings(f["geometry"]):
            ax.add_patch(Polygon(ring, closed=True, fc=fc, ec="#9A9A9A", lw=0.4))
    for f in rivers["features"]:
        if f["properties"].get("name") in ("Shabeelle", "Jubba", "Shebele", "Genale"):
            g = f["geometry"]
            for ln in ([g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]):
                xs, ys = zip(*ln)
                ax.plot(xs, ys, color=BLUE, lw=1.1)
    # Label offsets (degrees) chosen so that town names do not collide at 11 point.
    towns = {"Kismaayo": (0.2, -0.35), "Boosaaso": (-1.2, 0.3), "Berbera": (-0.3, 0.3), "Hargeisa": (-1.3, -0.5),
             "Garoowe": (0.2, 0.1), "Baydhabo": (0.2, 0.15), "Beledweyne": (0.25, 0.05), "Jawhar": (0.25, 0.0),
             "Ceerigaabo": (-0.9, -0.55), "Gaalkacyo": (0.2, 0.05)}
    for f in places["features"]:
        p = f["properties"]
        if p.get("adm0name") not in ("Somalia", "Somaliland"):
            continue
        lon, lat = f["geometry"]["coordinates"]
        if p["name"] == "Mogadishu":
            ax.plot(lon, lat, marker="*", ms=16, color=RED, zorder=5)
            ax.annotate("Mogadishu: port and\nindustrial parks (outskirts)", (lon, lat), xytext=(lon + 1.0, lat - 1.6),
                        color=RED, arrowprops=dict(arrowstyle="-", color=RED, lw=0.8))
        elif p["name"] in towns:
            dx, dy = towns[p["name"]]
            ax.plot(lon, lat, marker="o", ms=4, color=NAVY, zorder=4)
            ax.text(lon + dx, lat + dy, p["name"], color=NAVY)
    ax.set_xlim(40.5, 51.8)
    ax.set_ylim(-2.0, 12.4)
    ax.set_aspect("equal")
    ax.axis("off")
    handles = [Patch(fc="#F3E3C3", ec="#9A9A9A", label="Frankincense areas named by the Export Strategy (Sanaag, Bari)"),
               Patch(fc="#DCEFD9", ec="#9A9A9A", label="Shabelle and Juba valleys (sesame, fruit, irrigation)"),
               Line2D([0], [0], color=BLUE, lw=1.2, label="Shabelle and Juba rivers"),
               Line2D([0], [0], marker="*", color="w", markerfacecolor=RED, ms=14, label="Parks and port (Mogadishu)"),
               Line2D([0], [0], color="w", label="Coastline of 3,300 km (fisheries)")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 0.0), ncol=1)
    ax.text(49.0, 3.4, "Indian Ocean", color=GREY, style="italic")
    ax.text(44.6, 11.9, "Gulf of Aden", color=GREY, style="italic")
    return fig


def _box(ax, xy, w, h, text, fc, tc="white"):
    ax.add_patch(FancyBboxPatch(xy, w, h, boxstyle="round,pad=0,rounding_size=0.04", fc=fc, ec="none"))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", color=tc)


def _arrow(ax, a, b, col=GREY):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=12, color=col, lw=1.2))


@figure("1.7", "From binding constraints to policy responses",
        "This policy.", "Schematic. Each response is developed in Part 3, Part 4 and Part 5.")
def fig_1_7(x: Ctx):
    fig, ax = plt.subplots(figsize=(WIDTH, 6.0))
    ax.set_xlim(0, 3.2)
    ax.set_ylim(0, 4.3)
    ax.axis("off")
    for x0, t, c in [(0.0, "Binding constraints", RED), (1.1, "Consequences", GREY), (2.2, "Policy responses", GREEN)]:
        ax.text(x0 + 0.5, 4.15, t, ha="center", fontweight="bold", color=c)
    rows = [("Costly, diesel-based electricity", "Light manufacturing cannot compete", "Solar and storage for the parks (Part 3)"),
            ("Raw exports: live animals, raw sesame and resin", "Value, jobs and hides leave the country",
             "Processing clusters and certification (Part 4)"),
            ("Imports meet most consumer demand", "Foreign exchange drain and a thin tax base",
             "Consumer staples and light manufacturing (Part 4)"),
            ("Floods, poor drainage and congested roads", "Disrupted park-to-port corridor and lost income",
             "Drainage, sewerage and electric buses (Part 5)")]
    for i, (a_, b_, c_) in enumerate(rows):
        y = 3.05 - i * 0.98
        for x0, txt, col in ((0.0, a_, RED), (1.1, b_, "#595959"), (2.2, c_, GREEN)):
            _box(ax, (x0, y), 1.0, 0.82, wrap(txt, 18), col)
        _arrow(ax, (1.0, y + 0.41), (1.1, y + 0.41))
        _arrow(ax, (2.1, y + 0.41), (2.2, y + 0.41))
    return fig


# --------------------------------------------------------------------------- Part 3

@figure("3.1", "What park solar power costs, and what it replaces",
        "Model base scenario (modelled estimate); World Bank, Somalia Economic Update 11 (2026), Table 4; Ministry of "
        "Energy generation plan (2025).",
        "Park solar and storage is the model's levelised cost in the base scenario (illustrative, not a forecast), built up "
        "from the annualised capital cost of PV and batteries and their operation and maintenance. Tariffs are averages; "
        "the source table does not state the year.")
def fig_3_1(x: Ctx):
    pv, bat, om = (x.M(f"climate.minigrid.lcoe_{p}_usd_per_kwh") * 100 for p in ("pv", "battery", "om"))
    rows = ["Park solar and storage\n(model, base scenario)", "Kenya, average tariff", "Diesel self-generation",
            "Somalia, lowest average tariff"]
    others = [x.C("C-0489"), x.C("D-0079"), x.C("C-0083")]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.6))
    ax.barh(0, pv, color=GREEN, height=0.6, label="PV capital")
    ax.barh(0, bat, left=pv, color="#6FA776", height=0.6, label="Battery capital")
    ax.barh(0, om, left=pv + bat, color="#B7D4BB", height=0.6, label="Operation and maintenance")
    ax.text(pv + bat + om + 1, 0, f"{pv + bat + om:.1f}", va="center")
    ax.barh([1, 2, 3], others, color=[BLUE, ORANGE, RED], height=0.6)
    for i, v in zip((1, 2, 3), others):
        ax.text(v + 1, i, f"{v:g}", va="center")
    ax.invert_yaxis()
    ax.set_yticks(range(4), rows)
    ax.set_xlim(0, 60)
    ax.set_xlabel("US cents per kWh")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=3)
    return fig


@figure("3.2", "Electricity demand of the industrial parks by cluster, 2032",
        "Model base scenario (modelled estimate).",
        "Demand is each production line's output multiplied by its electricity use per unit (design estimates; no metered "
        "Somali data exist). Illustrative, not a forecast.")
def fig_3_2(x: Ctx):
    names = [("c1", "Cluster 1: coastal export processing"), ("c2", "Cluster 2: riverine agro-processing"),
             ("c3", "Cluster 3: light manufacturing\nand consumer staples"), ("c4", "Cluster 4: business services")]
    vals = [x.M(f"climate.park_demand_gwh.{c}.2032") for c, _ in names]
    fig, ax = plt.subplots(figsize=(WIDTH, 3.2))
    ax.barh(range(4), vals, color=[NAVY, GREEN, BLUE, GREY], height=0.6)
    ax.invert_yaxis()
    ax.set_yticks(range(4), [n for _, n in names])
    hbar_labels(ax, vals, lambda v: f"{v:.1f}", 0.5)
    ax.set_xlim(0, max(vals) * 1.2)
    ax.set_xlabel("GWh a year")
    ax.grid(axis="y", visible=False)
    return fig


def _node(ax, xy, w, h, text, fc, tc="white", width=22):
    _box(ax, xy, w, h, wrap(text, width), fc, tc)
    return (xy[0], xy[1], w, h)


def _link(ax, a, b, label=None, side="right"):
    """Arrow from box a to box b (centres of facing edges), with an optional label beside its midpoint."""
    ax_, ay, aw, ah = a
    bx, by, bw, bh = b
    if abs((ay + ah / 2) - (by + bh / 2)) < 0.05:  # same row: horizontal arrow
        p0, p1 = ((ax_ + aw, ay + ah / 2), (bx, by + bh / 2)) if bx > ax_ else ((ax_, ay + ah / 2), (bx + bw, by + bh / 2))
    else:  # vertical arrow
        p0, p1 = ((ax_ + aw / 2, ay), (bx + bw / 2, by + bh)) if by < ay else ((ax_ + aw / 2, ay + ah), (bx + bw / 2, by))
    _arrow(ax, p0, p1)
    if label:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        ax.text(mx + (0.06 if side == "right" else -0.06), my, label, ha="left" if side == "right" else "right",
                va="center", color="#404040", style="italic")


@figure("3.3", "One power company for all the parks: contracts and finance",
        "This policy.",
        "Schematic. The park power company is licensed by the National Electricity Authority under the Electricity Act; "
        "carbon revenue under Article 6 depends on the Carbon Markets Act.")
def fig_3_3(x: Ctx):
    fig, ax = plt.subplots(figsize=(WIDTH, 6.4))
    ax.set_xlim(0, 3.3)
    ax.set_ylim(0, 4.4)
    ax.axis("off")
    gov = _node(ax, (0.0, 3.4), 1.0, 0.8, "Government: park land, licence, Article 6 authorisation", NAVY)
    fin = _node(ax, (2.3, 3.4), 1.0, 0.8, "DFIs, guarantees and private equity", BLUE)
    co = _node(ax, (1.15, 1.95), 1.0, 0.85, "Park power company (solar plus storage)", GREEN)
    park = _node(ax, (1.15, 0.2), 1.0, 0.8, "Park operator and tenant firms", "#595959")
    buyer = _node(ax, (2.3, 0.2), 1.0, 0.8, "Carbon credit buyers (Article 6)", ORANGE)
    _arrow(ax, (1.0, 3.8), (1.35, 2.8))
    ax.text(0.2, 3.05, "land lease and licence", color="#404040", style="italic")
    _arrow(ax, (2.3, 3.8), (1.95, 2.8))
    ax.text(2.2, 3.05, "equity and loans", color="#404040", style="italic")
    _link(ax, co, park, "power purchase\nagreement", side="left")
    _arrow(ax, (2.15, 2.1), (2.8, 1.0))
    ax.text(2.55, 1.55, "credits", color="#404040", style="italic")
    return fig


@figure("3.4", "Riverine irrigation: what was lost and what pumping costs farmers",
        "National Irrigation Policy (Ministry of Agriculture and Irrigation); Hiiraan Online news report (18 September 2026).",
        "Panel A: areas are pre-war estimates and a potential, not current figures. Panel B reports two individual farmers "
        "in Afgoye district quoted in a news report; it is illustrative, not a survey.")
def fig_3_4(x: Ctx):
    fig, (a, b) = plt.subplots(2, 1, figsize=(WIDTH, 5.0), gridspec_kw=dict(height_ratios=[1.3, 1], hspace=0.65))
    rows = [("Equipped for irrigation, 1984", x.C("C-0210"), GREY), ("Irrigated before the war", x.C("C-0206"), BLUE),
            ("Potential under pump or recession irrigation", x.C("C-0207"), GREEN)]
    vals = [v for _, v, _ in rows]
    a.barh(range(3), vals, color=[c for *_, c in rows], height=0.6)
    a.invert_yaxis()
    a.set_yticks(range(3), [n for n, *_ in rows])
    hbar_labels(a, vals, lambda v: f"{v:,.0f}", 10000)
    a.set_xlim(0, max(vals) * 1.25)
    a.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(200000))
    a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a.set_title("A. Irrigable area (hectares)")
    a.grid(axis="y", visible=False)
    f1, f2 = x.C("C-0530"), x.C("C-0531")
    b.barh([0, 1], [f1, f2], color=ORANGE, height=0.55)
    b.set_yticks([0, 1], ["Farmer 1, lower end of range", "Farmer 2, upper end of range"])
    b.invert_yaxis()
    hbar_labels(b, [f1, f2], lambda v: f"{v:g}", 8)
    b.set_xlim(0, f2 * 1.25)
    b.set_title("B. Cost per irrigation round with a fuel-powered pump (USD)")
    b.grid(axis="y", visible=False)
    return fig


@figure("3.5", "How much the budget depends on customs, 2024",
        "IMF, Somalia: Fourth Review under the Extended Credit Facility (2025), Table 2d.",
        "Federal Government and five Federal Member States; preliminary, cash basis; excludes Somaliland.")
def fig_3_5(x: Ctx):
    tax, trade, share = x.C("C-0537"), x.C("C-0424"), x.C("D-0080")
    fig, ax = plt.subplots(figsize=(WIDTH, 2.4))
    ax.barh([0, 1], [tax, trade], color=[GREY, NAVY], height=0.6)
    ax.set_yticks([0, 1], ["Tax revenue", "of which taxes on\ninternational trade"])
    ax.invert_yaxis()
    ax.text(tax + 6, 0, f"{tax:.1f}", va="center")
    ax.text(trade + 6, 1, f"{trade:.1f} ({share * 100:.1f}%)", va="center")
    ax.set_xlim(0, tax * 1.3)
    ax.set_xlabel("USD million")
    ax.grid(axis="y", visible=False)
    return fig


@figure("3.6", "The certification pathway for chilled meat exports to the Gulf",
        "Livestock Sector Development Strategy; Somali Standards and Quality Control Law; this policy.",
        "Schematic. Each step names the certificate or approval that Gulf buyers and regulators require, and the "
        "institution responsible.")
def fig_3_6(x: Ctx):
    x.C("C-0535")
    x.C("C-0195")
    fig, ax = plt.subplots(figsize=(WIDTH, 7.0))
    ax.set_xlim(0, 3.2)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    steps = [("Herds and markets", "Animal identification and traceability", NAVY),
             ("Quarantine and inspection", "Unified Animal Health Certificate from federal veterinarians", NAVY),
             ("Export abattoir in the park", "Halal, food safety (HACCP) and national standards", GREEN),
             ("Chilled cold chain to port or airport", "Temperature records and export documents", BLUE),
             ("Gulf import approval", "Plant listing by the importing country's regulator", ORANGE)]
    for i, (step, req, col) in enumerate(steps):
        y = 4.2 - i * 1.02
        _box(ax, (0.0, y), 1.25, 0.78, wrap(step, 20), col)
        _box(ax, (1.55, y), 1.65, 0.78, wrap(req, 28), "#EEF2F5", tc="black")
        _arrow(ax, (1.25, y + 0.39), (1.55, y + 0.39))
        if i < len(steps) - 1:
            _arrow(ax, (0.625, y), (0.625, y - 0.24))
    return fig


# --------------------------------------------------------------------------- registry

def main(argv=None):
    wanted = (argv if argv is not None else sys.argv[1:]) or list(FIGURES)
    x = Ctx()
    registry = []
    if REGISTRY.exists():
        registry = [r for r in yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or [] if r["id"] not in wanted]
    for fid in wanted:
        spec = FIGURES[fid]
        x.reset()
        path = save(spec["fn"](x), fid)
        src_ids = sorted(set().union(*[x.sources_of(c) for c in x.used_c]) | set(x.used_s)) if x.used_c else sorted(x.used_s)
        registry.append(dict(id=fid, title=spec["title"], file=path.relative_to(ROOT).as_posix(), claims=list(x.used_c),
                             model_outputs=list(x.used_m), scenario="base" if x.used_m else None, sources=src_ids,
                             source_line=spec["source"], note=spec["note"]))
        print(f"Figure {fid}: {path.relative_to(ROOT)} ({len(x.used_c)} claims, {len(x.used_m)} model outputs), audit passed")
    registry.sort(key=lambda r: [int(p) for p in r["id"].split(".")])
    REGISTRY.write_text("# Figure register (CLAUDE.md section 12A). Generated by tools/figures.py; do not edit by hand.\n"
                        + yaml.safe_dump(registry, sort_keys=False, allow_unicode=True, width=200), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
