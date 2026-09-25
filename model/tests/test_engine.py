"""Tests for the impact model's accounting rules (CLAUDE.md 13.1 and 13.3). Run: python -m unittest discover -s model/tests"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model import engine  # noqa: E402


def aid_for(name):
    _, _, inputs = engine.load_registers(ROOT)
    return next(e["ref"] for e in inputs if e["name"] == name)


def value_of(aid):
    _, assumptions, _ = engine.load_registers(ROOT)
    return engine._num(assumptions[aid]["value"])


class TestAccounting(unittest.TestCase):
    def setUp(self):
        self.d = {s: engine.compute_detail(s, ROOT) for s in ("low", "base", "high")}

    def test_national_is_sum_of_clusters_and_clusters_sum_of_lines(self):
        for d in self.d.values():
            for y in engine.YEARS:
                for m, v in d["national"][y].items():
                    self.assertAlmostEqual(v, sum(d["clusters"][c][y][m] for c in engine.CLUSTERS), places=6)
                for cid, (_, lines) in engine.CLUSTERS.items():
                    for m, v in d["clusters"][cid][y].items():
                        self.assertAlmostEqual(v, sum(d["lines"][ln][y][m] for ln in lines), places=6)

    def test_value_added_never_exceeds_gross_output(self):
        for d in self.d.values():
            for rows in d["lines"].values():
                for r in rows.values():
                    self.assertLessEqual(r["value_added"], r["gross_output"] + 1e-9)

    def test_import_substitution_and_exports_are_not_added_to_value_added(self):
        aid = aid_for("soap.domestic_share")
        base = engine.compute("base", ROOT)
        alt = engine.compute("base", ROOT, {aid: 0.5})
        self.assertAlmostEqual(base["soap.value_added.2032"]["value"], alt["soap.value_added.2032"]["value"])
        self.assertNotAlmostEqual(base["soap.import_substitution.2032"]["value"], alt["soap.import_substitution.2032"]["value"])

    def test_additionality_scales_impacts_but_not_investment(self):
        aid = aid_for("c1.additionality")
        full = engine.compute("base", ROOT, {aid: 1.0})
        half = engine.compute("base", ROOT, {aid: 0.5})
        self.assertAlmostEqual(half["c1.value_added.2032"]["value"] * 2, full["c1.value_added.2032"]["value"])
        self.assertAlmostEqual(half["c1.jobs.2032"]["value"] * 2, full["c1.jobs.2032"]["value"])
        self.assertAlmostEqual(half["c1.investment.cumulative"]["value"], full["c1.investment.cumulative"]["value"])

    def test_minigrid_output_is_not_counted_as_gdp(self):
        aid = aid_for("minigrid.solar_share")
        a = engine.compute("base", ROOT, {aid: 0.5})
        b = engine.compute("base", ROOT, {aid: 0.85})
        self.assertAlmostEqual(a["national.value_added.2032"]["value"], b["national.value_added.2032"]["value"])
        self.assertLess(a["climate.minigrid.avoided_t.2032"]["value"], b["climate.minigrid.avoided_t.2032"]["value"])

    def test_forgone_exports_reduce_net_fx_not_value_added(self):
        aid = aid_for("meat.diversion_share")
        a = engine.compute("base", ROOT, {aid: 0.0})
        b = engine.compute("base", ROOT, {aid: 0.6})
        self.assertAlmostEqual(a["meat.value_added.2032"]["value"], b["meat.value_added.2032"]["value"])
        self.assertGreater(a["meat.net_fx.2032"]["value"], b["meat.net_fx.2032"]["value"])

    def test_scenarios_are_ordered(self):
        f = {s: engine.compute(s, ROOT) for s in ("low", "base", "high")}
        for key in ("national.value_added.2032", "national.jobs.2032", "climate.total.avoided_t.2032", "national.net_fx.2032"):
            self.assertLessEqual(f["low"][key]["value"], f["base"][key]["value"], key)
            self.assertLessEqual(f["base"][key]["value"], f["high"][key]["value"], key)

    def test_outputs_record_their_assumptions(self):
        out = engine.compute("base", ROOT)
        self.assertIn(aid_for("flour.price"), out["flour.value_added.2032"]["depends"])
        self.assertNotIn(aid_for("flour.price"), out["soap.value_added.2032"]["depends"])
        self.assertIn(aid_for("gdp.growth_extension"), out["national.va_share_gdp.2032"]["depends"])
        self.assertNotIn(aid_for("gdp.growth_extension"), out["national.va_share_gdp.2031"]["depends"])

    def test_build_schedule_must_not_fall(self):
        with self.assertRaises(ValueError):
            engine.compute("base", ROOT, {aid_for("build.share_2030"): 0.1})

    def test_waste_capture_below_break_even_increases_emissions(self):
        out = engine.compute("base", ROOT, {aid_for("waste.capture_efficiency"): 0.3})
        self.assertLess(out["climate.waste.avoided_per_tonne_waste"]["value"], 0)

    def test_banaadir_stoves_earn_no_credits_at_zero_fnrb(self):
        out = engine.compute("base", ROOT, {aid_for("cooking.banaadir_share"): 1.0})
        self.assertAlmostEqual(out["climate.cooking.stove_creditable_t.2032"]["value"], 0.0)

    def test_total_value_added_is_direct_plus_indirect_plus_induced(self):
        for d in self.d.values():
            for rows in d["lines"].values():
                for r in rows.values():
                    self.assertAlmostEqual(r["total_va"], r["value_added"] + r["indirect_va"] + r["induced_va"], places=6)
                    self.assertAlmostEqual(r["tax_revenue"], r["tax_gross"] - r["customs_forgone"], places=6)

    def test_no_induced_effect_when_all_spending_leaks_abroad(self):
        out = engine.compute("base", ROOT, {aid_for("induced.domestic_share"): 0.0})
        self.assertAlmostEqual(out["national.induced_va.2032"]["value"], 0.0)

    def test_no_indirect_effect_when_supply_is_not_additional(self):
        ov = {aid_for(f"{ln}.indirect_additional_share"): 0.0 for _, lines in engine.CLUSTERS.values() for ln in lines}
        out = engine.compute("base", ROOT, ov)
        self.assertAlmostEqual(out["national.indirect_va.2032"]["value"], 0.0)

    def test_indirect_and_induced_do_not_change_direct_value_added(self):
        a = engine.compute("base", ROOT, {aid_for("indirect.va_content"): 0.6})
        b = engine.compute("base", ROOT, {aid_for("indirect.va_content"): 0.95})
        self.assertAlmostEqual(a["national.value_added.2032"]["value"], b["national.value_added.2032"]["value"])
        self.assertLess(a["national.total_va.2032"]["value"], b["national.total_va.2032"]["value"])

    def test_line_additionality_overrides_cluster(self):
        a = engine.compute("base", ROOT, {aid_for("c3.additionality"): 0.5})
        b = engine.compute("base", ROOT, {aid_for("c3.additionality"): 1.0})
        self.assertAlmostEqual(a["pellets.value_added.2032"]["value"], b["pellets.value_added.2032"]["value"])
        self.assertLess(a["soap.value_added.2032"]["value"], b["soap.value_added.2032"]["value"])

    def test_pellets_replace_charcoal_not_imports(self):
        out = engine.compute("base", ROOT)
        self.assertAlmostEqual(out["pellets.import_substitution.2032"]["value"], 0.0)
        self.assertGreater(out["pellets.value_added.2032"]["value"], 0.0)

    def test_import_displacement_scales_import_substitution_only(self):
        aid = aid_for("dairy.import_displacement")
        a = engine.compute("base", ROOT, {aid: 0.4})
        b = engine.compute("base", ROOT, {aid: 0.8})
        self.assertAlmostEqual(a["dairy.import_substitution.2032"]["value"] * 2, b["dairy.import_substitution.2032"]["value"])
        self.assertAlmostEqual(a["dairy.value_added.2032"]["value"], b["dairy.value_added.2032"]["value"])

    def test_stoves_in_use_follow_factory_sales(self):
        a = engine.compute("base", ROOT, {aid_for("stoves.capacity"): 100000})
        b = engine.compute("base", ROOT, {aid_for("stoves.capacity"): 200000})
        self.assertAlmostEqual(a["climate.cooking.stoves_in_use.2032"]["value"] * 2, b["climate.cooking.stoves_in_use.2032"]["value"])
        self.assertLess(a["climate.cooking.avoided_t.2032"]["value"], b["climate.cooking.avoided_t.2032"]["value"])

    def test_stove_lifetime_limits_stock(self):
        short = engine.compute("base", ROOT, {aid_for("cooking.stove_lifetime_years"): 2})
        long_ = engine.compute("base", ROOT, {aid_for("cooking.stove_lifetime_years"): 5})
        self.assertLess(short["climate.cooking.stoves_in_use.2032"]["value"], long_["climate.cooking.stoves_in_use.2032"]["value"])

    def test_resin_diverted_from_raw_exports_reduces_net_fx(self):
        aid = aid_for("aromatics.diversion_share")
        a = engine.compute("base", ROOT, {aid: 0.7})
        b = engine.compute("base", ROOT, {aid: 1.0})
        self.assertGreater(a["aromatics.net_fx.2032"]["value"], b["aromatics.net_fx.2032"]["value"])
        self.assertAlmostEqual(a["aromatics.value_added.2032"]["value"], b["aromatics.value_added.2032"]["value"])

    def test_park_solar_cost_is_built_up_from_capital_costs(self):
        lo = engine.compute("base", ROOT, {aid_for("minigrid.site_premium"): 0.15})
        hi = engine.compute("base", ROOT, {aid_for("minigrid.site_premium"): 0.6})
        self.assertLess(lo["climate.minigrid.lcoe_usd_per_kwh"]["value"], hi["climate.minigrid.lcoe_usd_per_kwh"]["value"])
        cheap = engine.compute("base", ROOT, {aid_for("finance.discount_rate"): 0.08})
        dear = engine.compute("base", ROOT, {aid_for("finance.discount_rate"): 0.14})
        self.assertLess(cheap["climate.minigrid.lcoe_usd_per_kwh"]["value"], dear["climate.minigrid.lcoe_usd_per_kwh"]["value"])
        self.assertGreater(cheap["climate.minigrid.cost_saving.2032"]["value"], dear["climate.minigrid.cost_saving.2032"]["value"])

    def test_avoided_flood_losses_are_not_value_added(self):
        a = engine.compute("base", ROOT, {aid_for("resilience.drainage_coverage"): 0.15})
        b = engine.compute("base", ROOT, {aid_for("resilience.drainage_coverage"): 0.5})
        self.assertAlmostEqual(a["national.total_va.2032"]["value"], b["national.total_va.2032"]["value"])
        self.assertLess(a["resilience.avoided_losses.2032"]["value"], b["resilience.avoided_losses.2032"]["value"])
        self.assertAlmostEqual(a["resilience.bcr"]["value"], b["resilience.bcr"]["value"])  # scale does not change the ratio

    def test_pv_is_sized_to_park_demand(self):
        lo = engine.compute("base", ROOT, {aid_for("garments.kwh_per_unit"): 1000})
        hi = engine.compute("base", ROOT, {aid_for("garments.kwh_per_unit"): 3000})
        self.assertLess(lo["climate.minigrid.pv_mw"]["value"], hi["climate.minigrid.pv_mw"]["value"])
        self.assertAlmostEqual(lo["climate.minigrid.lcoe_usd_per_kwh"]["value"], hi["climate.minigrid.lcoe_usd_per_kwh"]["value"])
        out = engine.compute("base", ROOT)
        parts = sum(out[f"climate.minigrid.lcoe_{p}_usd_per_kwh"]["value"] for p in ("pv", "battery", "om"))
        self.assertAlmostEqual(parts, out["climate.minigrid.lcoe_usd_per_kwh"]["value"])


if __name__ == "__main__":
    unittest.main()
