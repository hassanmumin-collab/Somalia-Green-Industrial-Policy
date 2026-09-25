# Progress log

## 2026-09-23: Phase 0 (setup and verifier)

Done
- Renamed `CLAUDE md.md` to `CLAUDE.md` so Claude Code loads it automatically at the start of every session.
- Python 3.12 virtual environment in `.venv` (created with uv), PyYAML 6.0.3, PyMuPDF 1.28.2. Pandoc 3.11 installed for the current user with winget. PDF export uses the installed Microsoft Word.
- Directory structure per CLAUDE.md section 4. Empty registers created.
- `tools/verify.py` (22 checks, four modes), `tools/extract.py`, `tools/build.py`, `tools/hook.py`.
- Test suite in `tools/tests/`: passing and failing fixtures for every check, plus extraction, build and hook tests.
- Fact-checker subagent in `.claude/agents/fact-checker.md`.
- Hooks in `.claude/settings.json` (PostToolUse on Write|Edit|MultiEdit, Stop).

Blocked
- Nothing.

Needs Hassan
- Checkpoint 0 approved on 2026-09-23 ("Start phase 1").

## 2026-09-23: Phase 1 (document inventory)

Done
- 114 documents downloaded to `sources/raw/`, hashed, extracted to `sources/text/` and registered in `data/sources.yaml`. 7 documents registered as not obtained.
- New tools: `tools/fetch.py` (download, hash, extract, show title page; retries once) and `tools/winocr.py` (Windows built-in OCR, used because Tesseract has no per-user installer). OCR'd pages are saved as images in `sources/text/<ID>_pages/` for the fact-checker.
- Verifier now accepts an `ocr_pages` list per source and warns only for claims on those pages. Test added; 89 tests pass.
- `reports/source_inventory.md` written.
- The full NTP PDF (163 MB) is excluded from git; its hash is in the register.

Blocked
- IMF web pages and the CDM methodology database block automated access. IMF reports were obtained through the IMF eLibrary and the IMF SDMX API instead.
- ReliefWeb API requires a registered app name.

Needs Hassan (Checkpoint 1)
- Review the inventory and confirm the list before extraction begins.
- Tier rulings for foreign government material (S-096) and SDRB web articles (S-074 to S-077).
- Supply, if possible: MCS Technology Analysis Playbook, Investment Law 2025, LT-LEDS, Blue Economy Strategy, Carbon Markets bill draft, Banadir plans, English texts of the Electricity Act and Industrial Development Policy, any national energy policy.

- 2026-09-23: MCS Playbook supplied by Hassan via sources/inbox/; registered as S-119 (Tier 5, method only). 115 obtained, 6 not obtained.

## 2026-09-23: Phase 2 (claims extraction)

Done
- 234 claims (229 source, 5 derived) extracted from 43 sources through tools/claimkit.py, each verified before entry.
- Independent fact-check of every claim in 8 batches plus 3 re-check rounds; all 234 now pass. 28 corrected after fails or queries. Verdicts in reports/factcheck/.
- 14 conflicts recorded in data/conflicts.yaml (one resolved as not a conflict).
- Gaps listed in reports/figure_gaps.md. Checkpoint summary in reports/checkpoint_2.md.
- Verifier improvements (CSV fields, tolerance, glued units, capital suffixes, hyphen ranges, quote_context); 94 tests pass.
- Sources added: S-122, S-123 (Central Bank annual reports 2019 and 2020).
- Note: the fact-checker agent file was created mid-session, so its checks ran through general-purpose agents given the same instructions. It will be available as a named agent from the next session.

Needs Hassan (Checkpoint 2)
- Approve the conflict resolutions; decide X-013 (population).
- Decide how to handle plant-benchmark gaps before the model.
- Approve the UN Comtrade pull and the derived diesel generation cost.

- 2026-09-24: Hassan's Checkpoint 2 decisions recorded: population uses NDC 3.0 (X-013); benchmark gaps handled by targeted search, then wide-range assumptions; UN Comtrade pull and diesel cost approved; other resolutions approved.

## 2026-09-24: Phase 2 follow-up and Phase 3 (model)

Done
- Diesel generation cost taken from the Ministry of Energy plan's stated USD 400 per MWh (C-0230), so no derivation was needed.
- UN Comtrade mirror data: S-124 (exports to Somalia by 35 reporters; Gulf meat and live-animal imports; page 2 adds head counts) and S-146 (partners' imports from Somalia; leather prices). Scripts: tools/comtrade_pull.py, tools/comtrade_pull_2.py.
- Plant benchmarks: IFC and MIGA disclosures (S-128, S-130 to S-138), ILRI abattoirs (S-125), UNIDO tanning (S-126), trade media for sesame (S-129, Tier 4). S-127 (World Bank cold chain) reviewed but not usable.
- Emission-factor sources: IPCC 2006 Vol 2 Ch 1 (S-139), UN IRES (S-141), UK DESNZ 2026 factors (S-142, S-143), IPCC AR5 WG1 Ch 8 (S-144), IPCC 2006 Vol 5 Ch 2 (S-145). S-140 fetched but not usable.
- Claims: 376 active (334 source, 42 derived), all fact-checked; 3 superseded (a dairy workforce figure belonged to the construction contractor). Verdicts: reports/factcheck/batch_09 to batch_11, recheck_04 to recheck_06.
- Conflicts X-015 (diesel emission factor), X-016 (Pearl Dairy cost), X-017 (DTRT cost and jobs) added as proposals.
- Tools: verifier reads "$98.8M" and space-grouped values ("74 100"); extractor reads .xlsx (openpyxl added to requirements). 98 tool tests pass.
- Model built: model/engine.py, model/run.py, model/inputs.yaml (159 inputs), data/assumptions.yaml (151 assumptions, none yet approved), model/tests/test_engine.py (11 tests pass). Outputs in model/outputs/ (CSV and gip_model.xlsx). Verifier passes with no warnings (no M-claims registered yet).
- Checkpoint package: reports/checkpoint_3.md.

Blocked
- IFPRI Kenya 2019 and Ethiopia 2022 SAM datasets: Harvard Dataverse requires a guestbook form with a name and email; not submitted on Hassan's behalf.
- Ethiopian Statistics Service website did not respond (manufacturing survey not obtained).

Needs Hassan (Checkpoint 3)
- Approve or amend the 151 assumptions, above all the capacities that set the policy's ambition.
- Approve conflict resolutions X-015 to X-017.
- Optionally download the IFPRI SAMs into sources/inbox/.
- Point to ministry data on waste tonnage, diesel pumps, charcoal prices and park solar resource.

## 2026-09-24: Model revision after Hassan's Checkpoint 3 comments

Hassan's instructions: GDP impact too low; add wider benefits (foreign exchange retained, tax base, household purchasing power); meat to focus on camel and cattle meat for premium markets; fish sector not visible; decision 2 (X-015 to X-017) delegated; IFPRI SAMs supplied; search for waste, pump, charcoal and solar data; model to IMF / World Bank analyst standard.

Done
- Sources added: S-147 and S-148 (IFPRI SAMs, supplied by Hassan), S-149 (World Bank, Light Manufacturing in Africa, supplied by Hassan), S-150 (Global Solar Atlas, Mogadishu), S-151 (World Bank riverine assessment; no pump data), S-152 (Frontiers 2026, Mogadishu waste).
- Claims C-0337 to C-0412 and D-0044 to D-0058: SAM value-added ratios, Gulf beef markets and prices, live cattle values, cattle and camel carcass weights and slaughter, solar yield, waste estimates. Conflict X-018 (waste) added; X-015 to X-017 resolved under Hassan's delegation.
- tools/sam_multipliers.py: SAM multiplier analysis (reports/sam_multipliers.md). numpy added to requirements.
- Model v2: meat line is chilled beef and camel meat; capacities tied to markets and NTP targets; SAM-based value-added ratios; indirect and induced value added, household income, gross tax and customs forgone, capital-goods imports, growth contribution; Monte Carlo (2,000 draws). 170 assumptions, 15 model tests pass. Revised reports/checkpoint_3.md.

Blocked
- Fact-check of the 91 new claims: the checking agent stopped at the account's monthly spend limit. Rerun when the limit resets.
- FSNAU market prices need an API key (Hassan). No source found for irrigation pump counts.

Needs Hassan
- Approve assumptions, the SAM-based multiplier method (deviation from CLAUDE.md 13.1 item 7), the fiscal framing and X-018.

## 2026-09-24: Third model revision (meat market share, frankincense, clean cooking manufacturing, delegated assumptions)

Hassan's instructions:
- Meat should aim at a real share of the USD 1.09bn GCC chilled beef market, on the strength of proximity.
- Assumptions are delegated ("think like the best economic analyst at IMF or World Bank").
- Decisions 2 to 4 approved: SAM multiplier method, fiscal framing, X-018.
- Add frankincense and myrrh value addition (essential oils) to light manufacturing.
- Recast clean cooking as manufacturing of jikos and pellets inside a cluster.

Done
- Sources and claims:
  - Sources added: S-153 (FAO NWFP 6; not cited), S-154 (FAO NWFP 1, frankincense chapter, OCR), S-155 (Boswellia sacra oil yield, PMC).
  - Claims added: C-0413 to C-0434 (frankincense, cookstoves, NDC briquettes, IMF trade taxes and imports, Kenya SAM wood and metals).
  - Derived claims added: D-0059 to D-0063 (effective customs rate 3.2 percent, wood and metal value-added ratios, live-export carcass equivalent, GCC chilled beef tonnage).
- Correction: live cattle and camel exports are 222,010 and 193,013 head (C-0055, C-0056), not "few" as the second revision said.
- Model v3:
  - Cluster 3 renamed "Light manufacturing and consumer staples", with new lines for aromatics, stoves and pellets.
  - Optional line-level additionality and import displacement.
  - The cooking module now runs on stove and pellet sales, and reports household fuel savings and the stove subsidy.
  - Meat capacity is 30,000 t with 40 percent diversion from live exports.
  - The customs rate comes from IMF data.
  - Supply checks against offtake, live exports, GCC tonnage and frankincense value.
  - 204 active assumptions (IDs stable; 3 cooking assumptions retired), all approved under delegation. 21 model tests pass.
- CLAUDE.md:
  - Section 10: clusters and clean cooking amended.
  - Section 11: clean-cooking Part folded into Part 4 and later parts renumbered.
  - Section 13.1 item 7: approved deviation noted.
- X-018 approved. Revised reports/checkpoint_3.md; the previous version is kept as reports/checkpoint_3_rev2.md.

Base 2032
- Total value added USD 206.8m, 0.85 percent of GDP (Monte Carlo 0.72 to 1.11 percent).
- Direct jobs 17,837.
- Net FX USD 239.7m.
- Avoided emissions 262,878 t CO2e.

- UN Comtrade pull 3 (S-156):
  - Pakistan supplies 37 percent of GCC chilled beef imports by value, at USD 5.02 per kg (D-0064 to D-0066). The meat price was lowered to USD 5,500 per t (Pakistan benchmark).
  - Somali resin sells at USD 11.44 per kg in France and Germany, and its essential oils at about USD 200 per kg (D-0068 to D-0070).
- Base 2032 after the price change: total value added USD 200.8m (0.82 percent of GDP; Monte Carlo 0.71 to 1.09 percent), net FX USD 227.4m.
- Fact-check: all 549 active claims pass (batches 12 to 15, recheck_07). Twelve first-round fails and queries were corrected and rechecked.

Blocked
- Irrigation pump counts. Charcoal price now anchored on FSNAU's February 2022 Banadir market update (S-078; D-0071), because the FSNAU API is limited to FAO partners and no current newspaper price was found.

## 2026-09-25: Phase 4 started (Part 1), with the presentation and urban-resilience clarifications

Hassan's instructions:
- The parks sit on the outskirts of Mogadishu and the port is in the city, so the urban package (drainage, sewerage, e-buses) protects livability and the park-to-port corridor from congestion and climate disruption. Quantify dollar losses per disruption.
- Energy cost is the most prohibitive factor, so stand-alone solar and storage for the parks is the first priority.
- Prioritise well-crafted charts, flow charts and maps; make the model legible; the document should match an IMF publication.
- All recorded in CLAUDE.md sections 10 and 12A.

Done
- Evidence:
  - Regional electricity tariffs (S-062 Table 4; C-0485 to C-0492).
  - Mogadishu average annual flood losses of USD 120 million and the L2 drainage cost-benefit analysis (S-064; C-0493 to C-0498, C-0504 to C-0506, D-0072).
  - 2023 Deyr floods R-PDNA (S-157; C-0499, C-0500, C-0527, C-0528).
  - NDC loss estimate (C-0501).
  - Port capacity (S-158; C-0502, C-0503).
  - GCC beef supplier shares (D-0073 to D-0075, D-0078).
  - Resin unit values (D-0076, D-0077).
  - Map layers (S-159 to S-162).
- Model:
  - Park solar cost now built up from capital costs, asset lives, O&M, site premium and the discount rate, instead of the ESMAP mini-grid comparator: base USD 0.115 per kWh.
  - New urban resilience module: avoided Mogadishu flood losses, drainage investment and benefit-cost ratio (base 1.57).
  - 213 active assumptions. 23 model tests pass.
- Tools:
  - tools/figures.py generates figures from the registers and records them in data/figures.yaml.
  - Verifier check 23 covers figures, with tests.
  - {{FIG n.n}} markers in chapters are expanded by build.py.
  - Citations: first full, then short, with consecutive tags merged and a References list.
  - tools/make_reference_docx.py provides IMF-style Word styles.
  - build.py --draft makes review drafts.
  - tools/register_outputs.py registers model outputs as M- claims (M-0001, M-0002).
- Part 1 drafted (report/chapters/01_part1_why.md) with seven figures, including a map and a flow chart. Draft built: report/build/Part1_draft.docx and .pdf.

In progress
- Independent fact-check of C-0485 to C-0529 and D-0072 to D-0079.

## 2026-09-25: Presentation fixes, Times New Roman, and Part 3 drafted

Presentation (Hassan's instructions)
- Figure text in Times New Roman at 11 pt.
- tools/figures.py audits every figure and refuses to save one with overlapping, clipped, off-bar, low-contrast or line-crossing text (tests in tools/tests/test_figures.py). Figures are also inspected visually.
- Body text in Times New Roman 12 pt (tools/make_reference_docx.py).
- Every in-text citation is a numbered footnote with a clickable link, opening PDFs at the cited page. Figure source lines carry their own footnotes.
- Repository pushed to GitHub (public, at Hassan's choice); stored sources kept byte-identical through .gitattributes.

Model
- Park solar capacity is now sized from demand: each line's output times its electricity use per unit, with 15 new design-estimate assumptions and a solar share. Base scenario: 70 GWh a year at full build-out, 27.6 MW of PV (was a fixed 40 MW), USD 0.115 per kWh, USD 39.4 million of investment.
- Irrigation assumptions anchored on Afgoye farm evidence (S-163).
- New outputs: cost components of park solar, park demand by cluster, irrigation fuel savings.
- M-0003 to M-0014 registered.

Part 3 drafted (report/chapters/03_part3_foundations.md)
- Sections: energy, solar irrigation and water governance, land, standards and certification, trade and customs.
- Six figures: cost build-up, demand by cluster, power company structure, irrigation, customs dependence, certification pathway.
- Box 3.1 explains the park solar cost calculation.
- New sources: S-163 (news, tier 4) and S-164 (preprint, tier 5).
- New claims: C-0530 to C-0544 and D-0080.
- Draft built: report/build/GIP_draft_parts_1_3.pdf.

Open
- Pump census and a park load study (both preparatory-period tasks).
- Land law is only a 2017 draft bill.

## 2026-09-25: Part 3 revised after Hassan's review (irrigation per hectare; benchmarked factory electricity)

- Irrigation is now modelled per hectare. Diesel per hectare comes from the water pumped (measured on 10 Afgoi sesame plots, S-164), the pumping head, the pump-set efficiency and diesel's energy content (UK factors, D-0086). Fuel is priced at the NBS Mogadishu diesel prices before and after the February 2026 shock (C-0039, C-0040), and solar cost per hectare comes from the Philippine NIA projects (S-165, D-0087/D-0088).
- Base results: 122 litres per hectare a year; fuel USD 73 to 182 per hectare a year; solar USD 191 per hectare a year (annualised). On fuel alone, solar is roughly break-even at the post-shock price.
- The programme is sized in hectares (20,000 by 2032) instead of an unknown pump count. Figure 3.4 panel B was replaced by a per-hectare comparison.
- The Philippine study (S-165) is used for engineering data only. Its headline saving assumes 24-hour diesel running without discounting, and its fuel-use figure is internally inconsistent.
- Factory electricity use is now benchmarked on IFC EHS Guidelines (meat, fish, dairy, vegetable oil), EU BAT levels for grain milling and the ZAK soap plant. Park demand is 62 GWh a year: 24.5 MW of PV and USD 35.0 million.
- No benchmark was found for garments, BPO, diapers, tanning and a few smaller lines. A load study remains necessary.
- New sources S-165 to S-169 and S-172; claims C-0545 to C-0564 and D-0081 to D-0092, all fact-checked (C-0547 and D-0081 superseded after the checker found a row misreading).

Open
- Pumping head and pump-set efficiency are engineering estimates, to be replaced by the pump survey.
- The 113,652-hectare Afgoi figure may be cultivable rather than irrigated land (FAO SWALIM 2012 not yet obtained).
- UNEP cleaner-production guides and Ramírez (2006) could not be downloaded (sites block automated access). Hassan could supply them to firm up the meat electricity share.
