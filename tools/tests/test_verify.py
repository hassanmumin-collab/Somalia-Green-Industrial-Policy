"""Verifier tests: one passing and at least one failing fixture per check (CLAUDE.md 7.3).

Run from the project root:  .venv/Scripts/python.exe -m unittest discover -s tools/tests -v
"""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import fixture  # noqa: E402
import verify  # noqa: E402

TODAY = dt.date(2026, 9, 23)


class Base(unittest.TestCase):
    def run_spec(self, s, mode="all", today=TODAY, claim_id=None):
        root = fixture.build(s)
        self.addCleanup(fixture.cleanup, root)
        self.root = root
        return verify.run(root, mode, claim_id=claim_id, today=today, write=True)

    @staticmethod
    def fails(p, check):
        return [i for i in p.issues if i.check == check and i.level == "fail"]

    @staticmethod
    def warns(p, check):
        return [i for i in p.issues if i.check == check and i.level == "warn"]

    def assertPasses(self, p, check):
        self.assertEqual(self.fails(p, check), [], f"check {check} should pass: {[i.line() for i in self.fails(p, check)]}")

    def assertFails(self, p, check):
        self.assertTrue(self.fails(p, check), f"check {check} should fail; issues were {[i.line() for i in p.issues]}")

    def chapter(self, s, text, name="01_part1.md"):
        s["chapters"][name] = "# Part 1\n\n" + text + "\n"
        return s


class TestBaseline(Base):
    def test_baseline_passes_every_check_in_final_mode(self):
        p = self.run_spec(fixture.spec(), mode="final")
        self.assertEqual([i.line() for i in p.issues if i.level == "fail"], [])
        self.assertTrue((self.root / "reports" / "verification_report.md").exists())


class TestSourceIntegrity(Base):
    def test_1_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 1)

    def test_1_fail_missing_field(self):
        s = fixture.spec()
        del fixture.get(s, "sources", "S-001")["publisher"]
        self.assertFails(self.run_spec(s), 1)

    def test_1_fail_bad_tier(self):
        s = fixture.spec()
        fixture.get(s, "sources", "S-001")["tier"] = 7
        self.assertFails(self.run_spec(s), 1)

    def test_1_pass_not_obtained_source_may_have_null_paths(self):
        s = fixture.spec()
        s["sources"].append({**fixture.source("S-004", "Missing plan", "Ministry", 1, "S-004.txt"),
                             "local_path": None, "text_path": None, "sha256": None, "extraction": None})
        self.assertPasses(self.run_spec(s), 1)

    def test_2_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 2)

    def test_2_fail_hash_mismatch(self):
        s = fixture.spec()
        fixture.get(s, "sources", "S-001")["sha256"] = "0" * 64
        self.assertFails(self.run_spec(s), 2)

    def test_2_fail_file_missing(self):
        s = fixture.spec()
        p = self.run_spec(s)
        (self.root / "sources" / "raw" / "S-001.txt").unlink()
        p = verify.run(self.root, "all", today=TODAY)
        self.assertFails(p, 2)

    def test_3_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 3)

    def test_3_fail_no_text_file(self):
        s = fixture.spec()
        del s["texts"]["S-003.txt"]
        self.assertFails(self.run_spec(s), 3)


class TestClaimIntegrity(Base):
    def test_4_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 4)

    def test_4_fail_unknown_source(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0002")["source_id"] = "S-999"
        self.assertFails(self.run_spec(s), 4)

    def test_4_fail_missing_field(self):
        s = fixture.spec()
        del fixture.get(s, "claims", "C-0002")["basis"]
        self.assertFails(self.run_spec(s), 4)

    def test_4_fail_source_not_obtained(self):
        s = fixture.spec()
        src = fixture.get(s, "sources", "S-003")
        src.update(local_path=None, text_path=None, sha256=None, extraction=None)
        self.assertFails(self.run_spec(s), 4)

    def test_4_pass_pending_claim_without_source(self):
        s = fixture.spec()
        s["claims"].append({"id": "C-0100", "statement": "Unknown figure", "value": None, "unit": "USD",
                            "period": "2025", "measure": "x", "basis": "actual", "source_id": None,
                            "page": None, "quote": None, "status": "pending", "verified_at": None,
                            "fact_checked": False})
        self.assertPasses(self.run_spec(s), 4)

    def test_5_pass_with_hyphenation_across_lines(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0001")["quote"] = "reached US$13.2 billion in 2025, according to the rebased estimates"
        self.assertPasses(self.run_spec(s), 5)

    def test_5_pass_with_ligatures_and_curly_quotes(self):
        # C-0003's quote uses plain "fi" and straight quotes; the source has ligatures and curly quotes.
        self.assertPasses(self.run_spec(fixture.spec()), 5)

    def test_5_ocr_warning_only_on_ocr_pages(self):
        s = fixture.spec()
        fixture.get(s, "sources", "S-001").update(extraction="ocr", ocr_pages=[3])
        fixture.get(s, "claims", "C-0003")["fact_checked"] = False
        p = self.run_spec(s)
        warned = {i.where for i in self.warns(p, 5)}
        self.assertIn("C-0003", warned)       # page 3 is OCR
        self.assertNotIn("C-0001", warned)    # page 2 has a text layer

    def test_5_fail_wrong_page(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0001")["page"] = 3
        p = self.run_spec(s)
        self.assertFails(p, 5)
        self.assertIn("page(s) [2]", self.fails(p, 5)[0].msg)

    def test_5_fail_altered_quote(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0001")["quote"] = "Nominal GDP at constant prices reached US$13.2 billion in 2025"
        self.assertFails(self.run_spec(s), 5)

    def test_6_pass_equivalent_form(self):
        s = fixture.spec()
        c = fixture.get(s, "claims", "C-0001")
        c.update(value=13200, unit="USD million")
        self.assertPasses(self.run_spec(s), 6)

    def test_6_pass_thousands_separator(self):
        self.assertPasses(self.run_spec(fixture.spec()), 6)  # C-0003: 45000 against "45,000"

    def test_6_csv_source_commas_are_field_separators(self):
        s = fixture.spec()
        src = fixture.get(s, "sources", "S-003")
        src["local_path"] = "sources/raw/S-003.csv"
        s["texts"]["S-003.txt"] += "SOM,NGDPD,2025,12956145000,9\n"
        c = fixture.claim("C-0009", "GDP 2025 (WEO)", 12956145000, "USD", "2025", "GDP WEO", "estimate",
                          "S-003", 1, "SOM,NGDPD,2025,12956145000,9", status="estimate")
        s["claims"].append(c)
        self.assertPasses(self.run_spec(s), 6)
        c["value"] = 12956145001
        self.assertFails(self.run_spec(s), 6)

    def test_5_quote_context_supplies_table_units(self):
        s = fixture.spec()
        s["texts"]["S-003.txt"] += "Country fNRB (%)\nMali 45\nSomalia 64\n"
        c = fixture.claim("C-0010", "fNRB Somalia", 64, "percent", "2025", "fNRB national", "estimate",
                          "S-003", 1, "Mali 45 Somalia 64", status="estimate")
        s["claims"].append(c)
        self.assertFails(self.run_spec(s), 7)          # no percent sign near the row
        c["quote_context"] = "Country fNRB (%)"
        self.assertPasses(self.run_spec(s), 7)
        c["quote_context"] = "Country fNRB (percent of total)"
        self.assertFails(self.run_spec(s), 5)          # context must be on the page

    def test_6_number_with_glued_unit(self):
        nums = [n.value for n in verify.find_numbers("equipped 200,000ha in 1984 and 5MW; the 5th plan")]
        self.assertIn(200000.0, nums)
        self.assertIn(5.0, nums)            # 5MW
        self.assertEqual(nums.count(5.0), 1)  # "5th" is not a number

    def test_6_hyphen_range_is_not_minus(self):
        nums = verify.find_numbers("costs (17%-59% lower) and growth of -2.1 percent")
        self.assertEqual([(n.value, n.negative) for n in nums], [(17.0, False), (59.0, False), (2.1, True)])

    def test_6_capitalised_scale_suffixes(self):
        nums = {n.value * n.scale for n in verify.find_numbers("~36K workers, a $8Bn market and $700Mn sales")}
        self.assertTrue({36000.0, 8e9, 7e8} <= nums)

    def test_numeric_reads_space_grouped_thousands_strictly(self):
        self.assertEqual(verify.numeric("74 100"), 74100.0)
        self.assertEqual(verify.numeric("1 234 567.5"), 1234567.5)
        self.assertIsNone(verify.numeric("2024 100"))   # first group longer than three digits
        self.assertIsNone(verify.numeric("74 10"))      # second group not three digits
        self.assertIsNone(verify.numeric("seventy"))

    def test_6_space_grouped_value_must_appear_verbatim(self):
        s = fixture.spec()
        c = fixture.get(s, "claims", "C-0001")
        c["value"] = "13 300"
        self.assertFails(self.run_spec(s), 6)   # fixture quote has no "13 300"

    def test_6_bare_capital_m_is_million_but_units_still_parse(self):
        found = verify.find_numbers("contributing $98.8M in investments from a 5MW plant")
        self.assertIn((98.8, 1e6), [(n.value, n.scale) for n in found])
        self.assertIn((5.0, 1.0), [(n.value, n.scale) for n in found])  # 5MW keeps its unit, not million

    def test_6_fail_value_differs(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0001")["value"] = 13.3
        self.assertFails(self.run_spec(s), 6)

    def test_6_fail_scale_differs(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0001")["unit"] = "USD million"  # 13.2 million is not 13.2 billion
        self.assertFails(self.run_spec(s), 6)

    def test_7_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 7)

    def test_7_fail_period(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0001")["period"] = "2024"
        self.assertFails(self.run_spec(s), 7)

    def test_7_fail_currency(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0001")["unit"] = "SOS billion"
        self.assertFails(self.run_spec(s), 7)

    def test_7_fail_percent(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0006")["unit"] = "index points"
        self.assertFails(self.run_spec(s), 7)

    def test_7_fail_physical_unit(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0003")["unit"] = "head"
        self.assertFails(self.run_spec(s), 7)

    def test_8_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 8)

    def test_8_fail_wrong_value(self):
        s = fixture.spec()
        fixture.get(s, "claims", "D-0001")["value"] = 13300
        self.assertFails(self.run_spec(s), 8)

    def test_8_fail_verified_from_estimate(self):
        s = fixture.spec()
        s["claims"].append({"id": "D-0002", "statement": "x", "formula": "C-0004 * 2", "value": 0.7,
                            "unit": "USD per kWh", "rounding": 2, "status": "verified"})
        self.assertFails(self.run_spec(s), 8)

    def test_9_pass_conflict_registered(self):
        s = fixture.spec()
        s["claims"].append(fixture.claim("C-0007", "GDP 2025 (other)", 13.2, "USD billion", "2025",
                                         "GDP at current prices", "actual", "S-001", 2,
                                         "Nominal GDP at current prices reached US$13.2 billion in 2025"))
        self.assertPasses(self.run_spec(s), 9)  # same value: no conflict

    def test_9_fail_duplicate_id(self):
        s = fixture.spec()
        s["claims"].append(dict(fixture.get(s, "claims", "C-0002")))
        self.assertFails(self.run_spec(s), 9)

    def test_9_fail_unregistered_conflict_then_pass_when_registered(self):
        s = fixture.spec()
        s["texts"]["S-003.txt"] += "Nominal GDP at current prices was USD 12.1 billion in 2025.\n"
        s["claims"].append(fixture.claim("C-0008", "GDP 2025 (IMF)", 12.1, "USD billion", "2025",
                                         "GDP at current prices", "actual", "S-003", 1,
                                         "Nominal GDP at current prices was USD 12.1 billion in 2025"))
        self.assertFails(self.run_spec(s), 9)
        s["conflicts"] = [{"id": "X-001", "claims": ["C-0001", "C-0008"], "used": "C-0001",
                           "resolution": "NBS rebased series is the official figure"}]
        self.assertPasses(self.run_spec(s), 9)


class TestReportIntegrity(Base):
    def test_10_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 10)

    def test_10_fail_unresolved_tag(self):
        s = self.chapter(fixture.spec(), "GDP was USD 13.2 billion in 2025 {{C-0999}}.")
        self.assertFails(self.run_spec(s), 10)

    def test_10_fail_malformed_tag(self):
        s = self.chapter(fixture.spec(), "GDP rose {{C-01}}.")
        self.assertFails(self.run_spec(s), 10)

    def test_10_final_fails_on_pending_claim_and_cannot_confirm(self):
        s = fixture.spec()
        s["claims"].append({"id": "C-0100", "statement": "x", "value": None, "unit": "USD", "period": "2025",
                            "measure": "x", "basis": "actual", "source_id": None, "page": None, "quote": None,
                            "status": "pending", "verified_at": None, "fact_checked": False})
        s["chapters"]["02_part3.md"] = "# Part 3\n\nThe plant count is unknown. I cannot confirm this {{C-0100}}.\n"
        self.assertEqual(self.fails(self.run_spec(s, mode="all"), 10), [])
        self.assertFails(self.run_spec(s, mode="final"), 10)

    def test_10_final_fails_when_not_fact_checked(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0002")["fact_checked"] = False
        self.assertFails(self.run_spec(s, mode="final"), 10)

    def test_11_pass_allowlist_years_and_labels(self):
        self.assertPasses(self.run_spec(fixture.spec()), 11)

    def test_11_fail_untagged_number(self):
        s = self.chapter(fixture.spec(), "The ministry employs 450 staff.")
        self.assertFails(self.run_spec(s), 11)

    def test_11_fail_untagged_year_like_quantity(self):
        s = self.chapter(fixture.spec(), "The parks will create 2000 jobs.")
        self.assertFails(self.run_spec(s), 11)

    def test_12_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 12)

    def test_12_fail_number_mismatch(self):
        s = self.chapter(fixture.spec(), "GDP reached USD 14.1 billion in 2025 {{C-0001}}.")
        self.assertFails(self.run_spec(s), 12)

    def test_12_fail_silent_rounding(self):
        s = self.chapter(fixture.spec(), "GDP reached USD 13 billion in 2025 {{C-0001}}.")
        self.assertFails(self.run_spec(s), 12)

    def test_12_share_may_be_written_as_percent(self):
        n = verify.find_numbers("36.9 percent")[0]
        self.assertTrue(verify.number_matches_value(n, 0.369, "share of GCC imports by value", rounding=3))
        self.assertFalse(verify.number_matches_value(n, 0.369, "USD million", rounding=3))
        wrong = verify.find_numbers("37.9 percent")[0]
        self.assertFalse(verify.number_matches_value(wrong, 0.369, "share of GCC imports by value", rounding=3))

    def test_13_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 13)

    def test_13_fail_estimate_unlabelled(self):
        s = self.chapter(fixture.spec(), "According to industry sources, diesel costs USD 0.35 per kWh {{C-0004}}.")
        self.assertFails(self.run_spec(s), 13)

    def test_13_fail_illustrative_unlabelled(self):
        s = self.chapter(fixture.spec(), "In the base scenario, value added is a modelled estimate of USD 2.5 million {{M-0001}}.")
        self.assertFails(self.run_spec(s), 13)

    def test_14_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 14)

    def test_14_fail_projection_as_fact(self):
        s = self.chapter(fixture.spec(), "Real GDP growth will be 4.0 percent in 2026 {{C-0005}}.")
        self.assertFails(self.run_spec(s), 14)

    def test_14_fail_projection_via_derived_claim(self):
        s = fixture.spec()
        s["claims"].append({"id": "D-0003", "statement": "Growth doubled", "formula": "C-0005 * 2",
                            "value": 8.0, "unit": "percent", "rounding": 1, "status": "verified"})
        s = self.chapter(s, "Double the growth rate gives 8.0 percent {{D-0003}}.")
        self.assertFails(self.run_spec(s), 14)

    def test_15_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 15)

    def test_15_fail_unattributed_tier4(self):
        s = self.chapter(fixture.spec(), "Diesel generation is estimated to cost USD 0.35 per kWh {{C-0004}}.")
        self.assertFails(self.run_spec(s), 15)

    def test_16_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 16)

    def test_16_fail_tier4_in_executive_summary(self):
        s = fixture.spec()
        s["chapters"]["00_executive_summary.md"] += (
            "\nAccording to industry estimates, diesel power is estimated to cost USD 0.35 per kWh {{C-0004}}.\n")
        self.assertFails(self.run_spec(s), 16)

    def test_17_no_warning_for_recent_data(self):
        self.assertEqual(self.warns(self.run_spec(fixture.spec()), 17), [])

    def test_17_warns_on_old_data(self):
        p = self.run_spec(fixture.spec(), today=dt.date(2030, 1, 1))
        self.assertTrue(self.warns(p, 17))
        self.assertEqual(self.fails(p, 17), [])

    def test_18_pass_including_numeric_en_dash_range(self):
        s = self.chapter(fixture.spec(), "The policy covers 2028–2032.")
        self.assertPasses(self.run_spec(s), 18)

    def test_18_fail_em_dash(self):
        s = self.chapter(fixture.spec(), "The parks are sited in Mogadishu — near the port.")
        self.assertFails(self.run_spec(s), 18)

    def test_18_fail_en_dash_as_dash(self):
        s = self.chapter(fixture.spec(), "The parks are sited in Mogadishu – near the port.")
        self.assertFails(self.run_spec(s), 18)

    def test_18_warns_on_formulaic_construction(self):
        s = self.chapter(fixture.spec(), "The policy is not only green but also industrial.")
        p = self.run_spec(s)
        self.assertTrue(self.warns(p, 18))


class TestModelIntegrity(Base):
    def test_19_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 19)

    def test_19_fail_hard_coded_number(self):
        s = fixture.spec()
        s["engine"] = s["engine"].replace('a["A-001"]["value"]', "0.25")
        self.assertFails(self.run_spec(s), 19)

    def test_19_pass_marked_structural_literal(self):
        s = fixture.spec()
        s["engine"] += "\nYEARS = range(2028, 2033)  # allow-literal: policy period\n"
        self.assertPasses(self.run_spec(s), 19)

    def test_19_fail_input_not_claim_or_assumption(self):
        s = fixture.spec()
        s["model_inputs"].append({"name": "mystery", "ref": "C-0999"})
        self.assertFails(self.run_spec(s), 19)

    def test_19_fail_input_is_unverified_claim(self):
        s = fixture.spec()
        s["model_inputs"].append({"name": "diesel", "ref": "C-0004"})  # status estimate
        self.assertFails(self.run_spec(s), 19)

    def test_19_fail_assumption_outside_range(self):
        s = fixture.spec()
        fixture.get(s, "assumptions", "A-001")["value"] = 0.5
        self.assertFails(self.run_spec(s), 19)

    def test_20_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 20)

    def test_20_fail_stale_output(self):
        s = fixture.spec()
        fixture.get(s, "claims", "M-0001")["value"] = 3.0
        s["chapters"]["01_part1.md"] = s["chapters"]["01_part1.md"].replace("| 2.5 {{M-0001}}", "| 3.0 {{M-0001}}")
        self.assertFails(self.run_spec(s), 20)

    def test_21_pass(self):
        self.assertPasses(self.run_spec(fixture.spec(), mode="final"), 21)

    def test_21_unapproved_assumption_warns_in_all_fails_in_final(self):
        s = fixture.spec()
        fixture.get(s, "assumptions", "A-001")["approved_by_hassan"] = False
        p = self.run_spec(s, mode="all")
        self.assertEqual(self.fails(p, 21), [])
        self.assertTrue(self.warns(p, 21))
        self.assertFails(self.run_spec(s, mode="final"), 21)

    def test_22_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 22)

    def test_22_fail_unlabelled_model_output(self):
        s = self.chapter(fixture.spec(), "Value added reaches an illustrative USD 2.5 million {{M-0001}}.")
        self.assertFails(self.run_spec(s), 22)

    def test_22_fail_wrong_scenario_name(self):
        s = self.chapter(fixture.spec(), "In the high scenario, value added is an illustrative USD 2.5 million {{M-0001}}.")
        self.assertFails(self.run_spec(s), 22)

    def test_23_pass(self):
        self.assertPasses(self.run_spec(fixture.spec()), 23)

    def test_23_fail_unregistered_figure_marker(self):
        s = fixture.spec()
        s["chapters"]["01_part1.md"] = s["chapters"]["01_part1.md"].replace("{{FIG 1.1}}", "{{FIG 1.2}}")
        self.assertFails(self.run_spec(s), 23)

    def test_23_fail_unknown_claim(self):
        s = fixture.spec()
        s["figures"][0]["claims"] = ["C-0999"]
        self.assertFails(self.run_spec(s), 23)

    def test_23_fail_untraced_number_in_note(self):
        s = fixture.spec()
        s["figures"][0]["note"] = "GDP of USD 14.9 billion."
        self.assertFails(self.run_spec(s), 23)

    def test_23_fail_missing_image(self):
        s = fixture.spec()
        s["figures"][0]["file"] = "report/figures/missing.png"
        root = fixture.build(s)
        (root / "report" / "figures" / "missing.png").unlink()
        try:
            from tools import verify
            p = verify.run(root, "all", write=False)
            self.assertTrue([i for i in p.issues if i.check == 23 and i.level == "fail"])
        finally:
            fixture.cleanup(root)


class TestModesAndCli(Base):
    def test_exit_codes(self):
        root = fixture.build(fixture.spec())
        self.addCleanup(fixture.cleanup, root)
        self.assertEqual(verify.main(["--all", "--root", str(root), "--today", "2026-09-23", "--quiet"]), 0)
        (root / "report" / "chapters" / "09_bad.md").write_text("# Bad\n\nThere are 12 parks.\n", encoding="utf-8")
        self.assertEqual(verify.main(["--all", "--root", str(root), "--quiet"]), 2)
        report = (root / "reports" / "verification_report.md").read_text(encoding="utf-8")
        self.assertIn("Result: FAIL", report)

    def test_claim_mode(self):
        s = fixture.spec()
        fixture.get(s, "claims", "C-0002")["value"] = 9.9
        p = self.run_spec(s, mode="claim", claim_id="C-0002")
        self.assertFails(p, 6)
        p = verify.run(self.root, "claim", claim_id="C-0001", today=TODAY)
        self.assertEqual([i for i in p.issues if i.level == "fail"], [])

    def test_hook_mode_checks_named_chapter(self):
        s = self.chapter(fixture.spec(), "There are 12 parks.", name="05_part4.md")
        root = fixture.build(s)
        self.addCleanup(fixture.cleanup, root)
        p = verify.run(root, "hook", files=[str(root / "report" / "chapters" / "05_part4.md")], today=TODAY)
        self.assertTrue(self.fails(p, 11))


if __name__ == "__main__":
    unittest.main()
