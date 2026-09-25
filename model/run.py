"""Run the model: scenarios, consistency checks, sensitivity analysis and exports (CSV and Excel) to model/outputs/.

Usage: python model/run.py
"""
from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from model import engine  # noqa: E402

OUT = ROOT / "model" / "outputs"
SCENARIOS = ("low", "base", "high")
METRICS = ["volume", "gross_output", "value_added", "indirect_va", "induced_va", "total_va", "household_income",
           "import_substitution", "exports", "imported_inputs", "forgone_exports", "net_fx", "jobs", "investment",
           "capital_goods_imports", "tax_gross", "customs_forgone", "tax_revenue"]
KEY_OUTPUTS = [("national.value_added.2032", "Direct value added 2032 (USD million)"),
               ("national.total_va.2032", "Total value added incl. indirect and induced 2032 (USD million)"),
               ("national.total_va_share_gdp.2032", "Total value added as share of GDP 2032"),
               ("national.household_income.2032", "Household income 2032 (USD million)"),
               ("national.tax_revenue.2032", "Net tax revenue 2032 (USD million)"),
               ("national.jobs.2032", "Direct jobs 2032"),
               ("national.net_fx.2032", "Net foreign-exchange effect 2032 (USD million)"),
               ("climate.total.avoided_t.2032", "Avoided emissions 2032 (t CO2e)")]
TOP_N = 15  # allow-literal: number of assumptions shown in the sensitivity summary
MC_DRAWS = 2000  # allow-literal: Monte Carlo draws
MC_SEED = 20260924  # allow-literal: fixed random seed for reproducibility
PCTL = (10, 50, 90)  # allow-literal: percentiles reported
MARKET_SHARE_FLAG = 0.2  # allow-literal: flag chilled meat exports above a fifth of the GCC chilled beef market
SUPPLY_SHARE_FLAG = 0.25  # allow-literal: flag plants needing more than a quarter of cattle and camel offtake
TOL = 1e-6  # allow-literal: numerical tolerance for accounting identities

# Market and supply checks: line -> (claim ids whose values bound domestic sales, scale to USD, label)
MARKET = {"soap": (["D-0018"], engine.MILLION, "soap imports 2023, lower bound (D-0018)"),
          "diapers": (["D-0021"], engine.MILLION, "HS 9619 imports 2023, lower bound (D-0021)"),
          "garments": (["D-0023"], engine.MILLION, "apparel imports 2023, lower bound (D-0023)"),
          "flour": (["C-0142"], engine.THOUSAND, "wheat flour imports 2024 (C-0142)"),
          "dairy": (["C-0139"], engine.THOUSAND, "whole milk powder imports 2024 (C-0139)"),
          "sesame_oil": (["C-0148", "C-0149"], engine.THOUSAND, "palm oil and vegetable oil imports 2024 (C-0148, C-0149)"),
          "soap_detergent": (["D-0018", "D-0020"], engine.MILLION, "soap and detergent imports 2023, lower bounds (D-0018, D-0020)")}


def claim_value(claims, cid):
    """Claim value in base units: a unit beginning 'million' or 'thousand' (for example 'million head') is scaled."""
    c = claims[cid]
    unit = str(c.get("unit", "")).lower()
    scale = engine.MILLION if unit.startswith("million") else engine.THOUSAND if unit.startswith("thousand") else 1
    return engine._num(c["value"]) * scale


def checks(detail, claims):
    rows = []
    Y = engine.YEARS
    for y in Y:
        for m in METRICS + ["net_fx"]:
            nat = detail["national"][y][m]
            cl = sum(detail["clusters"][c][y][m] for c in engine.CLUSTERS)
            rows.append(("national equals sum of clusters", f"{m} {y}", nat, cl, abs(nat - cl) <= TOL * max(1, abs(nat))))
            for cid, (_, lines) in engine.CLUSTERS.items():
                c = detail["clusters"][cid][y][m]
                s = sum(detail["lines"][ln][y][m] for ln in lines)
                if abs(c - s) > TOL * max(1, abs(c)):
                    rows.append(("cluster equals sum of lines", f"{cid} {m} {y}", c, s, False))
            va = detail["national"][y]["value_added"]
            go = detail["national"][y]["gross_output"]
            rows.append(("value added does not exceed gross output", f"{y}", va, go, va <= go + TOL))
    fy = engine.FINAL
    for ln, (ids, scale, label) in MARKET.items():
        if ln == "soap_detergent":
            continue
        dom = detail["lines"][ln][fy]["import_substitution"]
        market = sum(claim_value(claims, i) for i in ids) * scale
        rows.append((f"domestic sales of {ln} within current imports", f"{fy}: {label}", dom, market, dom <= market))
    seed = detail["lines"]["sesame"][fy]["volume"] + detail["lines"]["sesame_oil"][fy]["volume"]
    for cid in ("C-0127", "C-0157"):
        rows.append(("sesame seed needed within production estimate", f"{fy} against {cid}", seed, claim_value(claims, cid),
                     seed <= claim_value(claims, cid)))
    fish = detail["lines"]["fish"][fy]["volume"]
    rows.append(("fish processed within estimated domestic catch", f"{fy} against C-0153", fish, claim_value(claims, "C-0153"),
                 fish <= claim_value(claims, "C-0153")))
    meat_t = detail["lines"]["meat"][fy]["volume"]
    offtake_t = ((claim_value(claims, "C-0411") + claim_value(claims, "C-0055")) * claim_value(claims, "C-0409")
                 + (claim_value(claims, "C-0412") + claim_value(claims, "C-0056")) * claim_value(claims, "C-0410")) / engine.THOUSAND
    rows.append(("chilled meat within a quarter of cattle and camel offtake (slaughter plus live exports, carcass weight)",
                 f"{fy} against C-0411, C-0412, C-0055, C-0056", meat_t, offtake_t, meat_t <= offtake_t * SUPPLY_SHARE_FLAG))
    exp_t = meat_t * detail["lines"]["meat"][fy]["exports"] / max(detail["lines"]["meat"][fy]["gross_output"], TOL)
    gcc_t = claim_value(claims, "D-0063")
    rows.append(("chilled meat exports within a fifth of GCC chilled beef imports (tonnes)", f"{fy} against D-0063", exp_t, gcc_t,
                 exp_t <= gcc_t * MARKET_SHARE_FLAG))
    live_t = claim_value(claims, "D-0062")
    diverted = meat_t * detail["inputs"]["meat.diversion_share"]
    rows.append(("animals diverted from live export within current live cattle and camel exports (carcass weight)",
                 f"{fy} against D-0062", diverted, live_t, diverted <= live_t))
    aro = detail["lines"]["aromatics"][fy]["gross_output"]
    frank = claim_value(claims, "C-0413") * engine.MILLION
    rows.append(("aromatics output value within pre-drought frankincense production value", f"{fy} against C-0413", aro, frank,
                 aro <= frank))
    fish_target = claim_value(claims, "C-0180")
    rows.append(("fish processed within NTP 2029 fish production target", f"{fy} against C-0180", fish, fish_target, fish <= fish_target))
    return rows


def sensitivity(root):
    base = engine.compute("base", root)
    _, assumptions, inputs = engine.load_registers(root)
    used = sorted({e["ref"] for e in inputs if str(e["ref"]).startswith("A-")})
    rows = []
    for aid in used:
        a = assumptions[aid]
        lo, hi = (engine._num(x) for x in a["range"])
        if lo == hi:
            continue
        r_lo = engine.compute("base", root, {aid: lo})
        r_hi = engine.compute("base", root, {aid: hi})
        rec = {"id": aid, "parameter": a["parameter"], "low": lo, "base": engine._num(a["value"]), "high": hi}
        for key, _ in KEY_OUTPUTS:
            b = base[key]["value"]
            rec[key + ".at_low"] = r_lo[key]["value"]
            rec[key + ".at_high"] = r_hi[key]["value"]
            rec[key + ".swing"] = abs(r_hi[key]["value"] - r_lo[key]["value"])
            rec[key + ".base"] = b
        rows.append(rec)
    return rows


def monte_carlo(root):
    """Independent triangular draws (low, base, high) for every assumption with a range; build shares sorted by year."""
    import random
    rng = random.Random(MC_SEED)
    _, assumptions, inputs = engine.load_registers(root)
    used = sorted({e["ref"] for e in inputs if str(e["ref"]).startswith("A-")})
    build = [next(e["ref"] for e in inputs if e["name"] == f"build.share_{y}") for y in engine.YEARS]
    results = {k: [] for k, _ in KEY_OUTPUTS}
    for _ in range(MC_DRAWS):
        ov = {}
        for aid in used:
            a = assumptions[aid]
            lo, hi = (engine._num(x) for x in a["range"])
            if lo < hi:
                ov[aid] = rng.triangular(lo, hi, engine._num(a["value"]))
        shares = sorted(ov.get(b, engine._num(assumptions[b]["value"])) for b in build)
        ov.update(dict(zip(build, shares)))
        out = engine.compute("base", root, ov)
        for k in results:
            results[k].append(out[k]["value"])
    summary = []
    for k, lbl in KEY_OUTPUTS:
        v = sorted(results[k])
        q = [v[min(len(v) - 1, int(p / 100 * len(v)))] for p in PCTL]  # allow-literal: percent to fraction
        summary.append((k, lbl, *q))
    return summary


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    claims, assumptions, inputs = engine.load_registers(ROOT)
    details = {s: engine.compute_detail(s, ROOT) for s in SCENARIOS}
    flat = {s: engine.compute(s, ROOT) for s in SCENARIOS}

    long_rows = []
    for s, d in details.items():
        for ln, rows in d["lines"].items():
            cl = next(c for c, (_, lines) in engine.CLUSTERS.items() if ln in lines)
            for y in engine.YEARS:
                for m in METRICS:
                    long_rows.append((s, "line", cl, ln, y, m, rows[y][m]))
        for cid in engine.CLUSTERS:
            for y in engine.YEARS:
                for m in METRICS + ["net_fx"]:
                    long_rows.append((s, "cluster", cid, cid, y, m, d["clusters"][cid][y][m]))
        for y in engine.YEARS:
            for m in METRICS + ["net_fx"]:
                long_rows.append((s, "national", "all", "national", y, m, d["national"][y][m]))
            long_rows.append((s, "national", "all", "national", y, "va_share_gdp", d["national"][y]["value_added"] / d["gdp"][y]))
            long_rows.append((s, "macro", "all", "gdp", y, "gdp_usd", d["gdp"][y]))
            for mod, m in d["climate"].items():
                for k, v in m["rows"][y].items():
                    long_rows.append((s, "climate", mod, mod, y, k, v))
        for mod, m in d["climate"].items():
            long_rows.append((s, "climate", mod, mod, "", "cost_per_t", m["cost_per_t"]))
    write_csv(OUT / "results_long.csv", ["scenario", "level", "cluster", "name", "year", "metric", "value"], long_rows)
    write_csv(OUT / "outputs_flat.csv", ["scenario", "output_key", "value", "depends"],
              [(s, k, v["value"], " ".join(v["depends"])) for s, o in flat.items() for k, v in o.items()])

    chk = checks(details["base"], claims)
    write_csv(OUT / "checks_base.csv", ["check", "item", "model", "reference", "passed"], chk)
    failed_identity = [c for c in chk if not c[4] and ("sum" in c[0] or "exceed" in c[0])]  # allow-literal: tuple positions of the check record

    sens = sensitivity(ROOT)
    key0 = KEY_OUTPUTS[0][0]
    sens.sort(key=lambda r: -r[key0 + ".swing"])
    hdr = ["id", "parameter", "low", "base", "high"] + [f"{k}.{x}" for k, _ in KEY_OUTPUTS for x in ("at_low", "at_high", "swing")]
    write_csv(OUT / "sensitivity.csv", hdr, [[r.get(h) for h in hdr] for r in sens])

    mc = monte_carlo(ROOT)
    write_csv(OUT / "monte_carlo.csv", ["output_key", "label"] + [f"p{p}" for p in PCTL], mc)
    export_excel(details, flat, chk, sens, assumptions, inputs, claims, mc)
    print_summary(details, flat, chk, sens, mc)
    if failed_identity:
        print(f"ACCOUNTING IDENTITY FAILURES: {len(failed_identity)}")
        return 2  # allow-literal: process exit code
    return 0


def print_summary(details, flat, chk, sens, mc):
    print("Scenario summary, 2032 (impacts net of additionality; investment is cumulative 2028-2032, full cost)")
    for s in SCENARIOS:
        f = flat[s]
        v = lambda k: f[k]["value"]  # noqa: E731
        print(f"  {s:5s} VA USD {v('national.value_added.2032'):.1f}m ({v('national.va_share_gdp.2032'):.2%} of GDP), "
              f"jobs {v('national.jobs.2032'):,.0f}, investment USD {v('national.investment.cumulative'):,.0f}m, "
              f"net FX USD {v('national.net_fx.2032'):.1f}m, avoided {v('climate.total.avoided_t.2032'):,.0f} t CO2e, "
              f"climate investment USD {v('climate.total.investment.cumulative'):,.0f}m")
    for s in SCENARIOS:
        f = flat[s]
        v = lambda k: f[k]["value"]  # noqa: E731
        print(f"  {s:5s} TOTAL VA USD {v('national.total_va.2032'):.1f}m ({v('national.total_va_share_gdp.2032'):.2%} of GDP) = direct "
              f"{v('national.value_added.2032'):.1f} + indirect {v('national.indirect_va.2032'):.1f} + induced {v('national.induced_va.2032'):.1f}; "
              f"household income {v('national.household_income.2032'):.1f}m; net tax {v('national.tax_revenue.2032'):.1f}m")
    print("Monte Carlo (P10 / P50 / P90):")
    for k, lbl, *q in mc:
        print(f"  {lbl}: " + " / ".join(f"{x:,.4g}" for x in q))
    print("Checks failed (base):")
    for c in chk:
        if not c[4]:  # allow-literal: tuple position of the pass flag
            print(f"  {c[0]}: {c[1]} model {c[2]:,.1f} against {c[3]:,.1f}")  # allow-literal: tuple positions for display
    print(f"Sensitivity, top {TOP_N} by swing in 2032 value added:")
    for r in sens[:TOP_N]:
        print(f"  {r['id']} {r['parameter'][:70]:70s} swing {r[KEY_OUTPUTS[0][0] + '.swing']:.1f}")  # allow-literal: display width


def export_excel(details, flat, chk, sens, assumptions, inputs, claims, mc):
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "README"
    notes = [
        "Somalia Green Industrial Policy 2028-2032: economic and climate impact model (Phase 3 draft for Checkpoint 3)",
        "Illustrative scenario results, not forecasts. Every input is a verified claim or an assumption awaiting Hassan's approval.",
        "Sheets: Assumptions (data/assumptions.yaml), Inputs (model/inputs.yaml), Lines_<scenario> (product line by year),",
        "Clusters, Climate, Checks, Sensitivity. Money in current USD; value-added and trade figures are net of additionality.",
        "Import substitution and exports are reported separately from value added and are never added to it.",
        "Generated by model/run.py from model/engine.py.",
    ]
    for n in notes:
        ws.append([n])
    ws["A1"].font = Font(bold=True)

    ws = wb.create_sheet("Assumptions")
    cols = ["id", "model_input", "parameter", "value", "unit", "low", "high", "basis_claim", "comparator", "rationale", "approved_by_hassan"]
    ws.append(cols)
    for a in assumptions.values():
        ws.append([a["id"], a.get("model_input"), a["parameter"], engine._num(a["value"]), a["unit"], engine._num(a["range"][0]),
                   engine._num(a["range"][1]), a.get("basis_claim"), a.get("comparator"), a.get("rationale"), a.get("approved_by_hassan")])
    ws = wb.create_sheet("Inputs")
    ws.append(["name", "ref", "direction", "claim value (if a claim)", "claim statement (if a claim)"])
    for e in inputs:
        c = claims.get(e["ref"])
        ws.append([e["name"], e["ref"], e.get("direction"), engine._num(c["value"]) if c else None, c["statement"] if c else None])
    for s in SCENARIOS:
        ws = wb.create_sheet(f"Lines_{s}")
        ws.append(["cluster", "line", "year"] + METRICS + ["net_fx"])
        for cid, (_, lines) in engine.CLUSTERS.items():
            for ln in lines:
                for y in engine.YEARS:
                    r = details[s]["lines"][ln][y]
                    ws.append([cid, ln, y] + [r[m] for m in METRICS + ["net_fx"]])
    ws = wb.create_sheet("Clusters")
    ws.append(["scenario", "cluster", "name", "year"] + METRICS[1:] + ["net_fx", "va_share_gdp"])
    for s in SCENARIOS:
        d = details[s]
        for cid, (nm, _) in list(engine.CLUSTERS.items()) + [("national", ("National total", None))]:
            for y in engine.YEARS:
                r = d["clusters"][cid][y] if cid != "national" else d["national"][y]
                ws.append([s, cid, nm, y] + [r[m] for m in METRICS[1:] + ["net_fx"]] + [r["value_added"] / d["gdp"][y]])
    ws = wb.create_sheet("Climate")
    ws.append(["scenario", "module", "year", "avoided t CO2e", "investment USD", "cost per t CO2e (USD, MCS step 1b)"])
    for s in SCENARIOS:
        for mod, m in details[s]["climate"].items():
            for y in engine.YEARS:
                ws.append([s, mod, y, m["rows"][y]["avoided_t"], m["rows"][y]["investment"], m["cost_per_t"]])
    ws = wb.create_sheet("Checks")
    ws.append(["check", "item", "model", "reference", "passed"])
    for c in chk:
        ws.append(list(c))
    ws = wb.create_sheet("Sensitivity")
    hdr = ["id", "parameter", "low", "base", "high"] + [f"{lbl}: {x}" for _, lbl in KEY_OUTPUTS for x in ("at low", "at high", "swing")]
    ws.append(hdr)
    for r in sens:
        ws.append([r["id"], r["parameter"], r["low"], r["base"], r["high"]] +
                  [r[f"{k}.{x}"] for k, _ in KEY_OUTPUTS for x in ("at_low", "at_high", "swing")])
    ws = wb.create_sheet("MonteCarlo")
    ws.append(["output_key", "label"] + [f"P{p}" for p in PCTL])
    for r in mc:
        ws.append(list(r))
    for sheet in wb.worksheets:
        for cell in sheet[1]:
            cell.font = Font(bold=True)
    wb.save(OUT / "gip_model.xlsx")


if __name__ == "__main__":
    sys.exit(main())
