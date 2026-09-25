"""Economic and climate impact model for the Somalia Green Industrial Policy, 2028 to 2032 (CLAUDE.md section 13).

Contract (model/README.md): compute(scenario, root) returns {output_key: {"value": float, "depends": [assumption ids]}}.
Every number comes from model/inputs.yaml, which maps each input name to a verified claim (C-/D-) or an assumption (A-).
The code holds no numeric literals other than 0 and 1, except structural constants marked "allow-literal".

Scenarios. "base" uses each assumption's value. "low" and "high" take the end of each assumption's recorded range
that lowers or raises the policy's net benefits; the direction is declared per input in inputs.yaml
("up": a higher value raises benefits; "down": a higher value lowers them; "none": the value is not varied).
Verified claims do not vary across scenarios.

Accounting rules (CLAUDE.md 13.1 and 13.3):
- Gross output = volume x price. Value added (the GDP contribution) = gross output x value-added ratio.
- Import substitution (domestic sales that replace imports) and export earnings are reported separately from value
  added and never added to it. Net foreign-exchange effect = import substitution + exports - imported inputs
  - baseline exports forgone (for example live animals diverted to slaughter, raw sesame diverted to hulling).
- Impacts are measured against a no-policy baseline: every product-line impact (output, value added, trade, jobs)
  is multiplied by the cluster's additionality share (the share of the activity that would not happen without the
  policy). Investment required is the full capital cost of the modelled capacity and is not scaled. A line may
  carry its own additionality in place of its cluster's (pellets largely replace domestic charcoal).
- Only domestic sales that replace imports count as import substitution: a line may declare the share
  (import_displacement; default all). Pellets replace domestic charcoal, not imports.
- Clean cooking is supplied by Cluster 3 manufacturing (efficient stoves, biomass pellets and briquettes). The climate
  module counts the additional stoves in use (sales over the stove's life) and the charcoal the pellets replace, and
  reports household fuel savings and the subsidy needed to bring the stove price to an affordable level. These are
  not added to value added.
- Byproducts count once: hides in tanning (not meat); tallow in soap (not meat); sesame cake and wheat bran in
  animal feed, which the model does not value.
- Solar mini-grid output is a cost saving for the clusters, not extra GDP.
- National totals are the sum of cluster totals.
- Indirect and induced effects are reported separately from direct value added (CLAUDE.md 13.1 item 7). Indirect value
  added = domestic input purchases x share of that supply which is additional x value-added content of domestic
  supply chains (anchored on IFPRI SAM Type I coefficients for Kenya and Ethiopia, tools/sam_multipliers.py). Induced
  value added = household income from direct and indirect value added x k / (1 - h x k), where h is the household
  share of value added and k = marginal propensity to consume x domestic share of consumption x value-added content.
- Tax revenue = total value added x Somalia's average revenue-to-GDP ratio, less customs duty forgone on displaced
  imports. It is indicative: no statutory tax schedule is modelled.
"""
from __future__ import annotations

from pathlib import Path

import yaml

YEARS = list(range(2028, 2033))  # allow-literal: policy period 2028 to 2032 (CLAUDE.md section 10)
FINAL = YEARS[-1]
MILLION = 1e6  # allow-literal: unit scale, USD to USD million
THOUSAND = 1e3  # allow-literal: unit scale
HOURS_PER_YEAR = 8760  # allow-literal: hours in a 365-day year
KW_PER_MW = 1e3  # allow-literal: unit conversion
KWH_PER_MWH = 1e3  # allow-literal: unit conversion
AAL_BASE_YEAR = 2026  # allow-literal: year of the World Bank Mogadishu flood risk assessment (C-0493)

CLUSTERS = {
    "c1": ("Coastal export processing", ["meat", "tanning", "fish"]),
    "c2": ("Riverine agro-processing", ["sesame", "sesame_oil", "fruit"]),
    "c3": ("Light manufacturing and consumer staples",
           ["flour", "dairy", "soap", "diapers", "garments", "aromatics", "stoves", "pellets"]),
    "c4": ("Business services", ["bpo"]),
}
LINE_PARAMS = ["capacity", "utilisation", "price", "va_ratio", "jobs_per_unit", "capex_per_unit",
               "domestic_share", "imported_input_share", "indirect_additional_share"]
FORGONE_LINES = {"meat": ("meat.diversion_share", "meat.live_value_per_t"),
                 "sesame": ("sesame.diversion_share", "sesame.raw_value_per_t"),
                 "sesame_oil": ("sesame_oil.diversion_share", "sesame.raw_value_per_t"),
                 "tanning": ("tanning.diversion_share", "tanning.raw_value_per_unit"),
                 "aromatics": ("aromatics.diversion_share", "aromatics.raw_value_per_t")}


# --------------------------------------------------------------------------- inputs

_CACHE: dict = {}


def load_registers(root: Path):
    root = Path(root)
    files = [root / "data" / "claims.yaml", root / "data" / "assumptions.yaml", root / "model" / "inputs.yaml"]
    key = tuple((str(f), f.stat().st_mtime_ns) for f in files)
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = _load(root)
    return _CACHE[key]


def _load(root: Path):
    claims = {c["id"]: c for c in yaml.safe_load((root / "data" / "claims.yaml").read_text(encoding="utf-8")) or []}
    assumptions = {a["id"]: a for a in yaml.safe_load((root / "data" / "assumptions.yaml").read_text(encoding="utf-8")) or []}
    inputs = yaml.safe_load((root / "model" / "inputs.yaml").read_text(encoding="utf-8")) or []
    return claims, assumptions, inputs


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        return float(v.replace(" ", ""))
    raise ValueError(f"not numeric: {v!r}")


class Inputs:
    """Resolves input names to values for a scenario and records which assumptions each value depends on."""

    def __init__(self, scenario: str, root: Path, overrides: dict | None = None):
        if scenario not in ("low", "base", "high"):
            raise ValueError(f"unknown scenario {scenario!r}")
        self.claims, self.assumptions, entries = load_registers(root)
        self.entries = {e["name"]: e for e in entries}
        self.scenario = scenario
        self.overrides = overrides or {}

    def ref(self, name):
        return self.entries[name]["ref"]

    def get(self, name):
        e = self.entries.get(name)
        if e is None:
            raise KeyError(f"model input '{name}' is not in model/inputs.yaml")
        ref = e["ref"]
        if ref.startswith("A-"):
            a = self.assumptions[ref]
            if ref in self.overrides:
                return float(self.overrides[ref]), {ref}
            lo, hi = (_num(x) for x in a["range"])
            direction = e.get("direction", "up")
            if self.scenario == "base" or direction == "none":
                v = _num(a["value"])
            elif (self.scenario == "high") == (direction == "up"):
                v = hi
            else:
                v = lo
            return v, {ref}
        c = self.claims[ref]
        return _num(c["value"]) * float(e.get("scale", 1)), set()


class Tracker:
    """Small helper that collects values and their assumption dependencies."""

    def __init__(self, inputs: Inputs):
        self.inp = inputs
        self.deps: set = set()

    def __call__(self, name):
        v, d = self.inp.get(name)
        self.deps |= d
        return v

    def opt(self, name, default):
        """Optional input: its value if model/inputs.yaml lists it, otherwise the default."""
        return self(name) if name in self.inp.entries else default


# --------------------------------------------------------------------------- core calculations

def build_path(t: Tracker):
    """Cumulative share of 2032 capacity online at the end of each year, and the output factor for each year.

    Capacity commissioned during a year runs at the first-year factor of mature utilisation."""
    shares = [t(f"build.share_{y}") for y in YEARS]
    for a, b in zip(shares, shares[1:]):
        if b < a:
            raise ValueError("build schedule must not fall over time")
    first = t("build.first_year_factor")
    prev = [0.0] + shares[:-1]
    output_factor = [p + first * (s - p) for s, p in zip(shares, prev)]
    return shares, prev, output_factor


def economy_wide(t: Tracker):
    """Economy-wide coefficients for indirect, induced, fiscal and balance-of-payments effects."""
    va_content = t("indirect.va_content")
    hh = t("induced.household_share_of_va")
    k = t("induced.mpc") * t("induced.domestic_share") * va_content
    return dict(va_content=va_content, hh=hh, k=k, loop=k / (1 - hh * k),
                revenue=t("fiscal.revenue_ratio"), customs=t("fiscal.customs_rate_displaced"),
                capex_imports=t("bop.capex_import_share"))


def product_line(line: str, cluster: str, t: Tracker):
    p = {k: t(f"{line}.{k}") for k in LINE_PARAMS}
    # A line may carry its own additionality (for example pellets, which largely replace domestic charcoal).
    add = t.opt(f"{line}.additionality", None)
    if add is None:
        add = t(f"{cluster}.additionality")
    # Share of domestic sales that replaces imports; the rest replaces other domestic supply (default: all imports).
    displaces_imports = t.opt(f"{line}.import_displacement", 1.0)
    ew = economy_wide(t)
    shares, prev, factor = build_path(t)
    forgone = None
    if line in FORGONE_LINES:
        ds, rv = FORGONE_LINES[line]
        forgone = (t(ds), t(rv))
    rows = {}
    for i, y in enumerate(YEARS):
        volume = p["capacity"] * p["utilisation"] * factor[i]
        gross = volume * p["price"]
        va = gross * p["va_ratio"]
        domestic = gross * p["domestic_share"]
        exports = gross - domestic
        import_substitution = domestic * displaces_imports
        imported_inputs = gross * p["imported_input_share"]
        forgone_exports = volume * forgone[0] * forgone[1] if forgone else 0.0
        jobs = p["capacity"] * shares[i] * p["jobs_per_unit"]
        investment = p["capacity"] * (shares[i] - prev[i]) * p["capex_per_unit"]
        r = dict(volume=volume, gross_output=gross, value_added=va, import_substitution=import_substitution, exports=exports,
                 imported_inputs=imported_inputs, forgone_exports=forgone_exports, jobs=jobs, investment=investment)
        # Impacts are scaled by additionality; volume (for supply checks) and investment required are not.
        r = {k: (v if k in ("volume", "investment") else v * add) for k, v in r.items()}
        r["net_fx"] = r["import_substitution"] + r["exports"] - r["imported_inputs"] - r["forgone_exports"]
        # Indirect value added: domestic purchases of inputs (output less value added and imported inputs), counted
        # only for the share of supply that is additional, times the value-added content of domestic supply chains.
        domestic_inputs = max(0.0, r["gross_output"] - r["value_added"] - r["imported_inputs"])
        r["indirect_va"] = domestic_inputs * p["indirect_additional_share"] * ew["va_content"]
        # Induced value added: households spend the income they receive; only domestically produced consumption adds
        # value added, and the loop repeats (Keynesian closure with Somali import leakage).
        first_round_income = (r["value_added"] + r["indirect_va"]) * ew["hh"]
        r["induced_va"] = first_round_income * ew["loop"]
        r["total_va"] = r["value_added"] + r["indirect_va"] + r["induced_va"]
        r["household_income"] = r["total_va"] * ew["hh"]
        r["customs_forgone"] = r["import_substitution"] * ew["customs"]
        r["tax_gross"] = r["total_va"] * ew["revenue"]
        r["tax_revenue"] = r["tax_gross"] - r["customs_forgone"]
        r["capital_goods_imports"] = r["investment"] * ew["capex_imports"]
        rows[y] = r
    return rows


def climate_modules(t: Tracker, lines: dict):
    """Avoided emissions (t CO2e a year), investment (USD) and cost per tonne (USD per t CO2e), MCS Playbook step 1b."""
    shares, prev, factor = build_path(t)
    out = {}
    crf = lambda r, n: r / (1 - (1 + r) ** (-n))  # capital recovery factor  # noqa: E731

    # Solar mini-grids for the parks: incumbent is private diesel generation (MCS step 1a).
    ef = t("energy.diesel_ef_t_per_mwh")
    mw = t("minigrid.pv_mw")
    hours = HOURS_PER_YEAR
    mwh_full = mw * t("minigrid.capacity_factor") * hours * t("minigrid.diesel_displaced_share")
    premium = 1 + t("minigrid.site_premium")
    pv_kw = t("minigrid.pv_capex_per_kw") * premium
    bat_kw = t("minigrid.battery_kw_per_pv_kw") * t("minigrid.battery_capex_per_kw") * premium
    capex_kw = pv_kw + bat_kw
    # Levelised cost of the park solar-plus-storage supply, built up from capital cost, asset lives, O&M and the
    # discount rate (annualised cost per kW of PV / kWh generated per kW of PV a year).
    r_mg = t("finance.discount_rate")
    annual_cost_kw = (pv_kw * crf(r_mg, t("minigrid.pv_lifetime_years")) + bat_kw * crf(r_mg, t("minigrid.battery_lifetime_years"))
                      + capex_kw * t("minigrid.om_share"))
    lcoe_solar = annual_cost_kw / (t("minigrid.capacity_factor") * HOURS_PER_YEAR)
    cost_diesel = t("minigrid.diesel_cost_usd_per_mwh")
    kw_per_mw = KW_PER_MW
    kwh_per_mwh = KWH_PER_MWH
    mg = {}
    for i, y in enumerate(YEARS):
        mwh = mwh_full * factor[i]
        mg[y] = dict(mwh=mwh, avoided_t=mwh * ef, investment=mw * (shares[i] - prev[i]) * kw_per_mw * capex_kw,
                     cost_saving=mwh * (cost_diesel - lcoe_solar * kwh_per_mwh))
    out["minigrid"] = dict(rows=mg, cost_per_t=(lcoe_solar * kwh_per_mwh - cost_diesel) / ef, lcoe=lcoe_solar)

    # Solar irrigation replacing diesel pumps.
    pumps = t("irrigation.pumps")
    litres = t("irrigation.diesel_litres_per_pump")
    ef_l = t("fuel.diesel_kgco2e_per_litre") / THOUSAND
    fuel_price = t("fuel.diesel_price_usd_per_litre")
    pump_capex = t("irrigation.capex_per_pump")
    r, n = t("finance.discount_rate"), t("irrigation.lifetime_years")
    ir = {}
    for i, y in enumerate(YEARS):
        active = pumps * factor[i]
        ir[y] = dict(avoided_t=active * litres * ef_l, investment=pumps * (shares[i] - prev[i]) * pump_capex,
                     fuel_saving=active * litres * fuel_price)
    per_pump_t = litres * ef_l
    out["irrigation"] = dict(rows=ir, cost_per_t=(pump_capex * crf(r, n) - litres * fuel_price) / per_pump_t)

    # Waste: managed landfill with gas capture replacing open dumping. Long-run methane potential per tonne
    # deposited (IPCC FOD Lo); the reduction is committed over decades, not emitted in the year of deposit.
    lo_co2e = t("waste.lo_tco2e_per_t_mcf1")
    mcf_base, mcf_proj = t("waste.mcf_baseline"), t("waste.mcf_project")
    eta = t("waste.capture_efficiency")
    per_t = lo_co2e * (mcf_base - mcf_proj * (1 - eta))
    tonnes = t("waste.tonnes_per_year")
    wcap = t("waste.capex_per_t_per_year")
    ws = {}
    for i, y in enumerate(YEARS):
        ws[y] = dict(avoided_t=tonnes * factor[i] * per_t, investment=tonnes * (shares[i] - prev[i]) * wcap)
    out["waste"] = dict(rows=ws, per_tonne_waste=per_t,
                        cost_per_t=(wcap * crf(r, t("waste.lifetime_years"))) / per_t if per_t > 0 else float("nan"))

    # Electric buses on major corridors, replacing diesel buses.
    buses, km = t("ebus.buses"), t("ebus.km_per_bus")
    diesel_t = km * t("ebus.diesel_litres_per_km") * ef_l
    grid_share = 1 - t("ebus.solar_charged_share")
    elec_t = km * t("ebus.kwh_per_km") * grid_share * ef / kwh_per_mwh
    per_bus_t = diesel_t - elec_t
    eb = {}
    for i, y in enumerate(YEARS):
        eb[y] = dict(avoided_t=buses * factor[i] * per_bus_t,
                     investment=buses * (shares[i] - prev[i]) * t("ebus.capex_per_bus"))
    fuel_saved = km * t("ebus.diesel_litres_per_km") * fuel_price
    elec_cost = km * t("ebus.kwh_per_km") * lcoe_solar
    extra_capex = (t("ebus.capex_per_bus") - t("ebus.diesel_bus_capex")) * crf(r, t("ebus.lifetime_years"))
    out["ebus"] = dict(rows=eb, cost_per_t=(extra_capex + elec_cost - fuel_saved) / per_bus_t)

    # Clean cooking, supplied by the Cluster 3 manufacturing lines: efficient stoves made in the parks, and biomass
    # pellets and briquettes (Prosopis and crop residues) that replace charcoal from native woodland. Only additional
    # sales count (the line's additionality): some efficient stoves would be imported without the policy.
    co2_t = t("cooking.co2_per_t_charcoal")
    fnrb = t("cooking.fnrb_national")
    fnrb_banaadir = t("cooking.fnrb_banaadir_creditable")
    banaadir = t("cooking.banaadir_share")
    saved = t("cooking.charcoal_saved_t_per_stove")
    life = max(1, round(t("cooking.stove_lifetime_years")))
    charcoal_price_t = t("cooking.charcoal_price_usd_per_kg") * THOUSAND
    stove_price, affordable = t("stoves.price"), t("stoves.affordable_price")
    stove_add = t.opt("stoves.additionality", None)
    if stove_add is None:
        stove_add = t("c3.additionality")
    pellet_add = t.opt("pellets.additionality", None)
    if pellet_add is None:
        pellet_add = t("c3.additionality")
    displaced = t("pellets.charcoal_displaced_t_per_t")
    pellet_price = t("pellets.price")
    sold = [lines["stoves"][y]["volume"] * stove_add for y in YEARS]
    ck = {}
    for i, y in enumerate(YEARS):
        in_use = sum(sold[max(0, i - life + 1):i + 1])  # stoves last `life` years
        physical = in_use * saved * co2_t * fnrb
        creditable = in_use * saved * co2_t * ((1 - banaadir) * fnrb + banaadir * fnrb_banaadir)
        pellets_t = lines["pellets"][y]["volume"] * pellet_add
        charcoal_replaced = pellets_t * displaced
        pellet_avoided = charcoal_replaced * co2_t * fnrb
        ck[y] = dict(avoided_t=physical + pellet_avoided, stove_avoided_t=physical, stove_creditable_t=creditable,
                     pellet_avoided_t=pellet_avoided, stoves_in_use=in_use,
                     household_saving=in_use * saved * charcoal_price_t
                     + charcoal_replaced * charcoal_price_t - pellets_t * pellet_price,
                     subsidy=sold[i] * max(0.0, stove_price - affordable),
                     investment=0.0)  # plant capital costs are counted in the stove and pellet lines
    stove_cost_year = stove_price * crf(r, life)
    out["cooking"] = dict(rows=ck, cost_per_t=(stove_cost_year - saved * charcoal_price_t) / (saved * co2_t * fnrb))
    return out


def urban_resilience(t: Tracker):
    """Avoided flood losses in Mogadishu from trunk drainage (World Bank Expected Annual Damage approach, scaled up).

    Losses grow from the 2026 assessment baseline; drainage covers a share of them by 2032 (following the build path) and
    reduces losses there by the flood-reduction share. Avoided losses protect assets and incomes; they are reported
    separately and never added to value added."""
    shares, prev, factor = build_path(t)
    aal = t("resilience.aal_musd") * MILLION
    g = t("resilience.loss_growth")
    cover, cut = t("resilience.drainage_coverage"), t("resilience.flood_reduction")
    capex_ratio = t("resilience.capex_per_usd_avoided")
    full_avoided_base = aal * cover * cut  # at 2026 loss levels
    rows = {}
    for i, y in enumerate(YEARS):
        losses = aal * (1 + g) ** (y - AAL_BASE_YEAR)
        rows[y] = dict(losses=losses, avoided=losses * cover * cut * factor[i],
                       investment=full_avoided_base * capex_ratio * (shares[i] - prev[i]))
    # Benefit-cost ratio over the drains' life, at the model's discount rate, with losses growing as above and the
    # full programme in place from the end of the policy period.
    r, life = t("finance.discount_rate"), round(t("resilience.lifetime_years"))
    avoided_final = aal * (1 + g) ** (FINAL - AAL_BASE_YEAR) * cover * cut
    pv = sum(avoided_final * (1 + g) ** k / (1 + r) ** k for k in range(1, life + 1))
    capex_total = full_avoided_base * capex_ratio
    return dict(rows=rows, capex_total=capex_total, bcr=pv / capex_total if capex_total else float("nan"))


def gdp_path(inp: Inputs):
    """Nominal GDP by year (USD) and, per year, the assumptions it depends on (only the extension year has any)."""
    g, deps = {}, {}
    for y in YEARS[:-1]:
        t = Tracker(inp)
        g[y] = t(f"gdp.{y}")
        deps[y] = t.deps
    t = Tracker(inp)
    g[FINAL] = g[FINAL - 1] * (1 + t("gdp.growth_extension"))
    deps[FINAL] = deps[FINAL - 1] | t.deps
    return g, deps


# --------------------------------------------------------------------------- public interface

def compute_detail(scenario: str, root, overrides: dict | None = None):
    """Full results: per line, cluster and national rows by year, climate modules, GDP path and dependencies."""
    inp = Inputs(scenario, Path(root), overrides)
    res = {"lines": {}, "clusters": {}, "national": {}, "deps": {},
           "inputs": {name: inp.get(name)[0] for name in inp.entries}}  # resolved input values for this scenario
    for cid, (_, lines) in CLUSTERS.items():
        cl_rows = {y: {} for y in YEARS}
        cl_deps = set()
        for line in lines:
            t = Tracker(inp)
            rows = product_line(line, cid, t)
            res["lines"][line] = rows
            res["deps"][line] = t.deps
            cl_deps |= t.deps
            for y in YEARS:
                for k, v in rows[y].items():
                    cl_rows[y][k] = cl_rows[y].get(k, 0.0) + v
        res["clusters"][cid] = cl_rows
        res["deps"][cid] = cl_deps
    nat = {y: {} for y in YEARS}
    for cid in CLUSTERS:
        for y in YEARS:
            for k, v in res["clusters"][cid][y].items():
                nat[y][k] = nat[y].get(k, 0.0) + v
    res["national"] = nat
    res["deps"]["national"] = set().union(*(res["deps"][c] for c in CLUSTERS))
    res["gdp"], res["deps"]["gdp"] = gdp_path(inp)
    t = Tracker(inp)
    res["climate"] = climate_modules(t, res["lines"])
    res["deps"]["climate"] = t.deps | res["deps"]["stoves"] | res["deps"]["pellets"]
    t = Tracker(inp)
    res["resilience"] = urban_resilience(t)
    res["deps"]["resilience"] = t.deps
    return res


def compute(scenario: str, root=".", overrides: dict | None = None):
    """Flat output dictionary for the verifier and the report: {key: {"value", "depends"}}."""
    d = compute_detail(scenario, root, overrides)
    out = {}

    def put(key, value, deps):
        out[key] = {"value": float(value), "depends": sorted(deps)}

    gdp_deps = d["deps"]["gdp"]
    for y in YEARS:
        put(f"gdp.{y}", d["gdp"][y] / MILLION, gdp_deps[y])
    groups = [(line, d["lines"][line], d["deps"][line]) for line in d["lines"]]
    groups += [(cid, d["clusters"][cid], d["deps"][cid]) for cid in CLUSTERS]
    groups += [("national", d["national"], d["deps"]["national"])]
    for name, rows, deps in groups:
        for y in YEARS:
            r = rows[y]
            for k in ("gross_output", "value_added", "import_substitution", "exports", "imported_inputs",
                      "forgone_exports", "net_fx", "investment", "indirect_va", "induced_va", "total_va",
                      "household_income", "tax_gross", "tax_revenue", "customs_forgone", "capital_goods_imports"):
                put(f"{name}.{k}.{y}", r[k] / MILLION, deps)
            put(f"{name}.jobs.{y}", r["jobs"], deps)
            put(f"{name}.va_share_gdp.{y}", r["value_added"] / d["gdp"][y], deps | gdp_deps[y])
            put(f"{name}.total_va_share_gdp.{y}", r["total_va"] / d["gdp"][y], deps | gdp_deps[y])
            prev_total = rows[y - 1]["total_va"] if y > YEARS[0] else 0.0
            prev_gdp = d["gdp"][y - 1] if y > YEARS[0] else None
            if prev_gdp:
                put(f"{name}.growth_contribution_pp.{y}", (r["total_va"] - prev_total) / prev_gdp * (1e2), deps | gdp_deps[y - 1])  # allow-literal: percentage points
        put(f"{name}.investment.cumulative", sum(rows[y]["investment"] for y in YEARS) / MILLION, deps)
        for k in ("tax_gross", "customs_forgone", "tax_revenue", "net_fx", "capital_goods_imports", "total_va", "household_income"):
            put(f"{name}.{k}.cumulative", sum(rows[y][k] for y in YEARS) / MILLION, deps)
    cdeps = d["deps"]["climate"]
    total_avoided = {y: 0.0 for y in YEARS}
    total_inv = 0.0
    for mod, m in d["climate"].items():
        for y in YEARS:
            put(f"climate.{mod}.avoided_t.{y}", m["rows"][y]["avoided_t"], cdeps)
            total_avoided[y] += m["rows"][y]["avoided_t"]
        inv = sum(m["rows"][y]["investment"] for y in YEARS)
        total_inv += inv
        put(f"climate.{mod}.investment.cumulative", inv / MILLION, cdeps)
        put(f"climate.{mod}.cost_per_t", m["cost_per_t"], cdeps)
    for y in YEARS:
        put(f"climate.total.avoided_t.{y}", total_avoided[y], cdeps)
        put(f"climate.cooking.stove_creditable_t.{y}", d["climate"]["cooking"]["rows"][y]["stove_creditable_t"], cdeps)
        put(f"climate.minigrid.cost_saving.{y}", d["climate"]["minigrid"]["rows"][y]["cost_saving"] / MILLION, cdeps)
        ck = d["climate"]["cooking"]["rows"][y]
        put(f"climate.cooking.pellet_avoided_t.{y}", ck["pellet_avoided_t"], cdeps)
        put(f"climate.cooking.stoves_in_use.{y}", ck["stoves_in_use"], cdeps)
        put(f"climate.cooking.household_saving.{y}", ck["household_saving"] / MILLION, cdeps)
        put(f"climate.cooking.subsidy.{y}", ck["subsidy"] / MILLION, cdeps)
    put("climate.total.investment.cumulative", total_inv / MILLION, cdeps)
    put("climate.minigrid.lcoe_usd_per_kwh", d["climate"]["minigrid"]["lcoe"], cdeps)
    rdeps, rs = d["deps"]["resilience"], d["resilience"]
    for y in YEARS:
        put(f"resilience.flood_losses.{y}", rs["rows"][y]["losses"] / MILLION, rdeps)
        put(f"resilience.avoided_losses.{y}", rs["rows"][y]["avoided"] / MILLION, rdeps)
    put("resilience.avoided_losses.cumulative", sum(rs["rows"][y]["avoided"] for y in YEARS) / MILLION, rdeps)
    put("resilience.investment.cumulative", sum(rs["rows"][y]["investment"] for y in YEARS) / MILLION, rdeps)
    put("resilience.bcr", rs["bcr"], rdeps)
    put("climate.waste.avoided_per_tonne_waste", d["climate"]["waste"]["per_tonne_waste"], cdeps)
    return out
