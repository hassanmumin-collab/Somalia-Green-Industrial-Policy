#!/usr/bin/env python3
"""SAM multipliers from the stored IFPRI social accounting matrices (S-147 Kenya 2019, S-148 Ethiopia 2022).

Method (standard fixed-price SAM multiplier analysis, Pyatt and Round 1979; Breisinger, Thomas and Thurlow 2009,
IFPRI "Social Accounting Matrices and Multiplier Analysis"):
  A = column coefficients of the endogenous accounts (payment from column account to row account / column total).
  A shock of one unit of additional output in activity j pays A[:, j] to the endogenous accounts; the total flows are
  z = (I - A)^-1 A[:, j]. Leakages are payments to exogenous accounts (imports, taxes, savings, government).
  Type I (production linkages): endogenous = activities, commodities, transaction costs. Value added generated =
      direct VA of j + sum over activities a of (VA ratio of a x z_a).
  Type II (adds household income and spending): endogenous also includes factors, enterprises and households;
      value added generated = sum of payments received by factor accounts in z.
  Multiplier = value added generated / direct value added of j (value added at factor cost = factor payments).
Also reported: VA ratio (factor payments / gross output) and labour share of VA (labour / all factor payments).

Usage: python tools/sam_multipliers.py      (writes reports/sam_multipliers.md and reports/sam_multipliers.csv)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SAMS = {"Kenya 2019 (S-147)": ROOT / "sources/raw/S-147_IFPRI-SAM-Kenya-2019.csv",
        "Ethiopia 2022 (S-148)": ROOT / "sources/raw/S-148_IFPRI-SAM-Ethiopia-2022.csv"}
ACTIVITIES = {"afood": "Processed foods", "aoils": "Oilseeds", "afrui": "Fruits and nuts", "aocer": "Other cereals", "atext": "Textiles, clothing and footwear", "achem": "Chemicals and petroleum",
              "absrv": "Business services", "afish": "Fisheries", "acatt": "Cattle and raw milk", "aoliv": "Other livestock",
              "atrad": "Wholesale and retail trade", "atran": "Transportation and storage", "acons": "Construction",
              "awood": "Wood and paper products", "ametl": "Metal products", "aoman": "Other manufacturing", "afore": "Forestry"}


def load(path):
    rows = [r for r in csv.reader(open(path, encoding="utf-8-sig")) if len(r) > 1 and r[1].strip()]
    head = [h.strip() for h in rows[0]]
    codes = [r[1].strip() for r in rows[1:]]
    col = {c: i for i, c in enumerate(head)}
    names = [c for c in codes if c != "total"]
    totrow = rows[1 + codes.index("total")]
    printed_total = np.array([float(totrow[col[c]].replace(",", "")) if totrow[col[c]].strip() else 0.0 for c in names])
    n = len(names)
    T = np.zeros((n, n))
    for i, rc in enumerate(names):
        r = rows[1 + codes.index(rc)]
        for j, cc in enumerate(names):
            v = r[col[cc]].strip() if col[cc] < len(r) else ""
            T[i, j] = float(v.replace(",", "")) if v else 0.0
    return names, T, printed_total


def analyse(names, T, printed_total):
    """Column coefficients use the file's printed column totals (the Kenya file rounds cells to whole numbers)."""
    rowsum, colsum = T.sum(axis=1), T.sum(axis=0)
    imbalance = float(np.max(np.abs(rowsum - colsum) / np.maximum(colsum, 1e-12)))
    idx = {c: i for i, c in enumerate(names)}
    acts = [c for c in names if c.startswith("a")]
    comms = [c for c in names if c.startswith("c")]
    facs = [c for c in names if c.startswith("f")]
    hh = [c for c in names if c.startswith("hhd")]
    ent = [c for c in names if c == "ent"]
    trc = [c for c in names if c == "trc"]
    tot = printed_total
    A_full = T / np.where(tot == 0, 1, tot)
    va_ratio = {a: sum(A_full[idx[f], idx[a]] for f in facs) for a in acts}
    lab = [f for f in facs if f.startswith("flab")]
    out = {}
    for typ, endo in (("I", acts + comms + trc), ("II", acts + comms + trc + facs + ent + hh)):
        e = [idx[c] for c in endo]
        A = A_full[np.ix_(e, e)]
        L = np.linalg.inv(np.eye(len(e)) - A)
        for a in ACTIVITIES:
            if a not in idx:
                continue
            shock = A_full[e, idx[a]]
            z = L @ shock
            pos = {c: k for k, c in enumerate(endo)}
            direct = va_ratio[a]
            if typ == "I":
                total = direct + sum(va_ratio[x] * z[pos[x]] for x in acts)
            else:
                total = sum(z[pos[f]] for f in facs)
            out.setdefault(a, {})[f"va_mult_{typ}"] = total / direct if direct else float("nan")
    for a in ACTIVITIES:
        if a in idx:
            fac_tot = sum(T[idx[f], idx[a]] for f in facs)
            out[a]["va_ratio"] = va_ratio[a]
            out[a]["labour_share"] = sum(T[idx[f], idx[a]] for f in lab) / fac_tot if fac_tot else float("nan")
            out[a]["gross_output"] = tot[idx[a]]
    return out, imbalance


def main():
    rows, md = [], ["# SAM multipliers from the IFPRI matrices", "",
                    "Generated by tools/sam_multipliers.py from the stored files of S-147 and S-148. Method in the script "
                    "docstring. Value added at factor cost. Type I counts supplier (production) linkages; Type II adds the "
                    "spending of household income generated. Multipliers are comparator values for Kenya and Ethiopia, not "
                    "Somali estimates.", ""]
    for label, path in SAMS.items():
        names, T, printed = load(path)
        res, imb = analyse(names, T, printed)
        md += [f"## {label}", "", f"Largest row-column imbalance: {imb:.2%} of the account total.", "",
               "| Activity | VA ratio | Labour share of VA | VA multiplier, Type I | VA multiplier, Type II |", "|---|---|---|---|---|"]
        for a, nm in ACTIVITIES.items():
            if a in res:
                r = res[a]
                md.append(f"| {nm} ({a}) | {r['va_ratio']:.3f} | {r['labour_share']:.3f} | {r['va_mult_I']:.3f} | {r['va_mult_II']:.3f} |")
                rows.append([label, a, nm, r["va_ratio"], r["labour_share"], r["va_mult_I"], r["va_mult_II"], r["gross_output"]])
        md.append("")
    (ROOT / "reports" / "sam_multipliers.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    with (ROOT / "reports" / "sam_multipliers.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sam", "code", "activity", "va_ratio", "labour_share", "va_mult_I", "va_mult_II", "gross_output"])
        w.writerows(rows)
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
