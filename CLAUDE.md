# CLAUDE.md: Somalia Green Industrial Policy (Part 1: Full Policy Document)

This file sets the permanent rules for this project. Read it at the start of every session and follow it over any conflicting instinct to move fast. Accuracy takes precedence over speed in every decision.

## 1. Mission

Produce a full Green Industrial Policy for the Federal Republic of Somalia covering the policy period 2028 to 2032 (40 to 60 pages, English), for presentation to the President and for use by ministries, development partners and investors. A presidential brief and an interactive dashboard (Part 2) will be derived from this document later, so every figure must live in the shared data registers described below, never only in prose.

The document is a national policy, not a campaign document. Tone is neutral, institutional and evidence-led. It must remain credible after any change of government.

Owner and final reviewer: Hassan Mumin. Nothing is final until he signs off.

## 2. The accuracy standard

Every factual statement in the report must be traceable to a stored copy of a source document, at a specific page, supported by a verbatim quote that the verifier has matched against the extracted text of that document.

Be precise about what this guarantees. The verifier proves traceability: the figure exists in the cited source exactly as reported. It does not prove the source itself is correct, and it does not prove the source was interpreted correctly. Interpretation is covered by the independent fact-checker subagent (section 8) and by Hassan's review. Never describe the report as "100% factual" in the document itself. Describe it as "fully sourced and verified against the cited documents."

Rules that follow from this:

1. No figure, date, name, title, law number, ranking or quantitative comparison enters the report without a claim ID.
2. Never write a figure from memory, from a search snippet, or from an earlier conversation. Search snippets and summaries are leads only. Open the source, store it, extract it, quote it.
3. If a fact cannot be verified, write "I cannot confirm this" in the working draft and record the claim with status `unconfirmed`. Unconfirmed claims may not appear in the final build.
4. If two sources disagree, record both in `data/conflicts.yaml`, state the discrepancy in the text, and explain which figure the report uses and why.
5. Distinguish actuals from projections, targets and estimates. A ministry projection is never reported as an outcome.
6. Never round, convert currencies, convert units, or change years silently. Any transformation is a derived claim (section 5.3).

## 3. Source hierarchy

Record a tier for every source.

| Tier | Type | Examples |
|---|---|---|
| 1 | Official Federal Government of Somalia documents and statistics | Laws, national plans, NBS and Central Bank publications, NDC, ministry strategies |
| 2 | Official multilateral publications | IMF, World Bank, FAO, UN agencies, AfDB, UNFCCC |
| 3 | Peer-reviewed research and primary trade databases | Journal articles, UN Comtrade, FAOSTAT |
| 4 | Reputable media and industry bodies | Reuters, Bloomberg, industry associations |
| 5 | Other | Aggregator sites, blogs, commercial market reports |

Rules:
- Headline figures in the executive summary must come from Tier 1 or Tier 2.
- Use a Tier 4 or 5 source only when no higher-tier source exists, and label it in the text ("according to industry estimates").
- Prefer the primary dataset over an aggregator (UN Comtrade over OEC; FAOSTAT over a news article quoting FAO).
- Where a Tier 1 and a Tier 2 figure differ (for example NBS rebased GDP against IMF WEO), report both and explain.
- Where data covers only part of the country (for example Somaliland or a single Federal Member State), say so explicitly.

## 4. Repository structure

```
/sources/raw/            original downloaded files, never edited
/sources/text/           extracted text, one file per source, page markers preserved
/sources/inbox/          documents Hassan drops in manually
/data/sources.yaml       source register
/data/claims.yaml        claim register
/data/conflicts.yaml     conflicting figures and how they were resolved
/data/allowlist.yaml     numbers permitted without a claim tag (with a reason each)
/data/assumptions.yaml   model assumptions (section 5.4)
/model/                  economic and climate impact model (section 13)
/report/chapters/        one Markdown file per part of the policy
/report/template/        reference.docx for Word styling
/tools/verify.py         the accuracy and data verifier
/tools/extract.py        text extraction (PDF, DOCX, HTML; OCR fallback)
/tools/build.py          assembles chapters, resolves claim tags to footnotes, builds DOCX and PDF
/tools/tests/            verifier test suite
/reports/verification_report.md   latest verifier output
/reports/source_inventory.md      document inventory for Hassan's review
/.claude/settings.json   hooks
/.claude/agents/fact-checker.md   independent fact-checker subagent
```

## 5. Data registers

### 5.1 Source register (`data/sources.yaml`)

```yaml
- id: S-001
  title: "Exact title as printed on the document"
  publisher: "Issuing body"
  date_published: "YYYY-MM-DD or YYYY"
  url: "https://..."
  accessed: "YYYY-MM-DD"
  local_path: "sources/raw/S-001_short-name.pdf"
  text_path: "sources/text/S-001.txt"
  sha256: "..."
  tier: 1
  language: "en"
  coverage: "Federal / Somaliland / Puntland / Banadir / national"
  extraction: "text | ocr"
  notes: ""
```

### 5.2 Claim register (`data/claims.yaml`)

```yaml
- id: C-0001
  statement: "Plain-language statement as used in the report"
  value: 13.2
  unit: "USD billion"
  period: "2025"
  measure: "GDP at current prices"
  basis: "actual | projection | target | estimate"
  source_id: S-001
  page: 4
  quote: "Verbatim text copied from the source, long enough to be unambiguous"
  status: "verified | estimate | illustrative | pending | unconfirmed"
  verified_at: "YYYY-MM-DD"
  fact_checked: false
```

### 5.3 Derived claims

Any calculation (sum, share, growth rate, conversion, rounding, scenario) is a derived claim:

```yaml
- id: D-0001
  statement: "Staple imports listed total X"
  formula: "C-0010 + C-0011 + C-0012"
  value: 0.0
  unit: "USD million"
  rounding: 1
  status: "verified"
```

The verifier recomputes every derived claim from its inputs. Scenario outputs carry status `illustrative` and must be labelled "illustrative, not a forecast" in the text.

### 5.4 Assumption register (`data/assumptions.yaml`)

Every model input that is not a verified claim is an assumption:

```yaml
- id: A-001
  parameter: "Value-added ratio, meat processing"
  value: 0.0
  unit: "share of gross output"
  range: [0.0, 0.0]        # low and high values used in scenarios
  basis_claim: C-0123      # verified claim the value is drawn from, if any
  comparator: "Country, year and study the benchmark comes from"
  rationale: "Why this value applies to Somalia"
  approved_by_hassan: false
```

An assumption with no `basis_claim` is a judgment call and must be approved by Hassan before any model output that depends on it appears in the report.

### 5.5 Claim tags in the report

Every sentence containing a figure or verifiable fact carries a tag: `{{C-0001}}` or `{{D-0001}}`. The build step converts tags into footnotes: publisher, title, date, page, URL, accessed date.

## 6. Sourcing protocol (run every time information comes from a document)

Follow these steps in order, every time, with no shortcuts:

1. Download the document into `sources/raw/`. Never rely on a web page summary.
2. Compute its SHA-256 and register it in `data/sources.yaml`.
3. Extract text with `tools/extract.py` into `sources/text/`, preserving page markers. If OCR was needed, record it; OCR text requires the fact-checker to confirm figures against the page image.
4. Add the claim to `data/claims.yaml` with a verbatim quote and page number.
5. Run `python tools/verify.py --claim <ID>`. Fix any failure before continuing.
6. Only then use the claim tag in the report.

If a document cannot be obtained (paywalled, offline, broken link), register it with `local_path: null`, add it to the "Not obtained" section of `reports/source_inventory.md`, and ask Hassan whether he can supply it via `sources/inbox/`. Do not use its figures until the file is stored.

## 7. The accuracy and data verifier (`tools/verify.py`)

Build this before any content is drafted. Python 3, standard library plus PyYAML and PyMuPDF (and pytesseract only if OCR is needed).

### 7.1 Modes

- `verify.py --all`: full check of registers and report
- `verify.py --claim C-0001`: check one claim
- `verify.py --hook`: fast check used by hooks (registers plus changed chapters)
- `verify.py --final`: strictest mode, run before any build; also fails on `pending` and `unconfirmed` claims appearing in chapters

Exit code 0 on pass. Exit code 2 on failure, with a readable failure list on stderr. Every run writes `reports/verification_report.md`.

### 7.2 Checks

Source integrity
1. Every source has the required fields.
2. Every stored file exists and its SHA-256 matches the register.
3. Every source has an extracted text file.

Claim integrity
4. Every claim has the required fields and references an existing source.
5. The quote appears in the source text after normalisation (whitespace, line breaks, hyphenation at line ends, ligatures, curly quotes). When a page is given, the match must be on that page.
6. The claim's value appears inside the quote, allowing only declared equivalent forms (1,000 / 1000; "13.2 billion" / "13,200 million"). Any other difference fails.
7. Period and unit in the claim are consistent with the quote where the quote states them.
8. Derived claims recompute to the stated value within the declared rounding.
9. No duplicate claim IDs. No two claims with the same measure and period but different values unless listed in `data/conflicts.yaml`.

Report integrity
10. Every claim tag in the chapters resolves to an existing claim.
11. Every number in a chapter sentence is covered by a claim tag in that sentence, or is on `data/allowlist.yaml`. Years used as dates and heading numbers are allowed automatically.
12. Where a sentence is tagged, each number in it matches the value (or declared display form) of one of its tagged claims.
13. Claims with status `estimate` or `illustrative` appear only in sentences that say so ("estimated", "illustrative").
14. Claims with basis `projection` or `target` appear only in sentences that say so ("projected", "target").
15. Tier 4 and 5 claims appear only in sentences that attribute them.
16. Executive summary figures come only from Tier 1 or Tier 2 sources.
17. Flags data older than five years as a warning, not a failure.
18. Style lint: fails on em-dashes and en-dashes used as dashes; warns on "not only... but also" and similar formulaic constructions.

Model integrity
19. Every model input is either a verified claim or an assumption in `data/assumptions.yaml`. Hard-coded numbers in `/model/` fail.
20. Every model output used in the report is recomputed from the model and matches the stated value.
21. Outputs that depend on an assumption with `approved_by_hassan: false` fail in `--final` mode.
22. Model outputs appear only in sentences labelled "modelled estimate" or "scenario", and always with the scenario name (low, base or high).

### 7.3 Tests

Write `tools/tests/` with at least one passing and one failing fixture for each check. The verifier is not ready until all tests pass. Rerun the tests whenever the verifier changes.

## 8. Independent fact-checker subagent

Create `.claude/agents/fact-checker.md`, a subagent with read-only tools (Read, Grep, Glob). It has not seen the drafting and must not rely on the drafting agent's reasoning. For each claim it receives, it opens the source text at the cited page and answers:

- Does the quote support the statement exactly as written?
- Is the figure an actual, projection, target or estimate, and does the statement say so?
- Is the period right (calendar versus fiscal year, year of data versus year of publication)?
- Is the measure right (nominal versus real, current versus constant prices, gross versus net, stock versus flow)?
- Is the geographic scope right (Federal Somalia, Somaliland, a single state, Mogadishu or Banadir)?
- Is the currency right?
- Does the surrounding text of the source qualify or contradict the figure?

It returns pass, fail or query for each claim, with a reason. Set `fact_checked: true` only on pass. Run it on every claim before a chapter is marked complete, and again on the whole register before the final build.

## 9. Hooks

Configure `.claude/settings.json` so the verifier runs automatically. Check the current documentation at https://code.claude.com/docs/en/hooks before writing the file, since hook behaviour can change.

- PostToolUse, matcher `Write|Edit`: run `verify.py --hook` whenever a file in `data/`, `sources/` or `report/` changes. Failures are fed back so they are fixed immediately.
- Stop: run `verify.py --hook`; if it fails, block stopping so the failure is resolved. Read the `stop_hook_active` field from the hook input and exit 0 if it is already true, to prevent an endless loop; in that case write the open failures to `reports/verification_report.md` and report them to Hassan.
- Use `${CLAUDE_PROJECT_DIR}` in hook commands. Detect whether the machine uses `python` or `python3`.

`tools/build.py` must also call `verify.py --final` and refuse to build if it fails.

## 10. Policy content decisions (agreed with Hassan)

These are design decisions, not facts. They need no source, but any figure used to justify them does.

- All industrial parks are sited on the outskirts of Mogadishu, for proximity to the port (which is inside the city) and to national markets. Goods therefore move between the parks and the port through the city (clarified by Hassan Mumin, 2026-09-25).
- Cluster 1, Coastal export processing: halal meat processing and cold-chain export, focused on chilled beef and camel meat for Gulf markets, aiming at a significant share of GCC chilled beef imports on the strength of proximity (small ruminants stay in the live trade; amended by Hassan Mumin, 2026-09-24); hides and skins tanning (separate wing with its own effluent treatment); fish and seafood cold chain and processing; maritime services (longer horizon).
- Cluster 2, Riverine agro-processing (sourcing from the Shabelle and Jubba valleys): sesame processing (hulled seed, tahini, halva); edible oil (sesame oil pressing and refining); fruit processing and fresh fruit export revival.
- Cluster 3, Light manufacturing and consumer staples (renamed and extended by Hassan Mumin, 2026-09-24): flour milling (imported wheat grain plus domestic maize and sorghum, grain silos as a strategic reserve, fortified flour); camel milk and dairy processing; soap and detergents; diapers and hygiene products; baati and macawis garments; frankincense and myrrh value addition (grading, cleaning, essential oils and extracts, with resin sourced from the producing regions); clean cooking manufacturing (efficient cookstoves or jikos, and biomass pellets and briquettes from Prosopis and crop residues).
- Cluster 4, Business services: BPO.
- Energy is the binding constraint (Hassan Mumin, 2026-09-25): the cost of electricity is the most prohibitive factor for light manufacturing in Somalia, so stand-alone solar with battery storage for the parks is the first priority of the enabling infrastructure, and the policy must show the tariff gap (Somalia against regional competitors) and the cost of park solar power.
- Enabling infrastructure: solar mini-grids with battery storage sized to each park's load profile, procured as one vehicle; solar irrigation replacing diesel pumps in the Shabelle and Jubba valleys, with water governance; government land for the parks.
- Urban built environment (Mogadishu): drainage and flood management, sewerage and wastewater treatment, a waste processing plant with landfill gas capture, electric buses on a small number of major corridors. Purpose (Hassan Mumin, 2026-09-25): make the city livable, reduce congestion, and reduce the disruption that climate shocks (floods, waterlogging) cause to the city and to the park-to-port corridor. The policy must quantify the economic cost of disruption (US dollar losses per flood or disruption event, and per day of lost access or port throughput where sources allow) and present the urban investments as protecting the industrial strategy, not as a separate social programme.
- Clean cooking (amended by Hassan Mumin, 2026-09-24): treated as a manufacturing opportunity within Cluster 3, not a separate programme. The policy offers incentives for firms to manufacture efficient cookstoves and pellets in the parks, given available feedstock and a large domestic market; carbon finance (voluntary market) supports a purchase subsidy that brings stove prices to an affordable level. The policy states that Banaadir's creditable fNRB of zero limits carbon crediting for stoves sold in Mogadishu.
- Financing: Article 6 for solar mini-grids and solar irrigation (and possibly electric buses); voluntary carbon market for clean cooking and waste methane; Gulf joint ventures and FDI for the processing clusters; DFIs and donors for land, irrigation, certification and urban infrastructure; domestic and diaspora capital for consumer staples and BPO.
- Article 6 finance depends on Somalia's Carbon Markets Act (target: through Parliament by March 2027). The policy must state this dependency and distinguish mitigation Somalia needs for its own NDC from mitigation it can transfer.
- Policy period: 2028 to 2032. September 2026 to December 2027 is a preparatory period (policy adoption, Carbon Markets Act, land allocation, feasibility studies, investor engagement), so implementation starts on 1 January 2028 with the groundwork done. The policy must state how it aligns with the national development plan in force (the National Transformation Plan, if confirmed as covering 2025 to 2029) and with its successor.
- Partnership model for meat processing: minority joint venture with a Gulf processor, with certification and supply security as the value proposition.

## 11. Report structure

1. Executive summary
2. Part 1: Why Somalia needs a green industrial policy
3. Part 2: Vision and 2032 targets
4. Part 3: Enabling foundations (energy, solar irrigation, land, standards and certification, trade and customs)
5. Part 4: Productive sectors (Clusters 1 to 4, one profile each)
6. Part 5: Urban built environment (Mogadishu)
7. Part 6: Financing architecture
8. Part 7: Economic, employment and climate impact (from the model in section 13)
9. Part 8: Institutions and delivery
10. Part 9: Roadmap: preparatory period (2026 to 2027), Phase I foundations and first plants (2028 to 2029), Phase II scale-up (2030 to 2032), with a mid-term review in 2030
11. Part 10: Risks and mitigation

(Amended 2026-09-24: clean cooking moved into the Cluster 3 profile in Part 4, and the later parts renumbered.)
13. Annexes: project pipeline, financing matrix, cluster profiles, model methodology and assumptions, source list, verification statement

Targets in Part 2 are set only after the model in section 13 has run, and are drawn from its base scenario. Do not invent them.

## 12. Writing style

- Seasoned consultant register: direct, declarative sentences with varied structure.
- No em-dashes. No "not only... but also". No formulaic openers or closers.
- Objective. No opinion or speculation presented as fact. Recommendations are stated as policy recommendations.
- Plain English suitable for senior officials. Define every acronym on first use.

## 12A. Presentation standard (Hassan Mumin, 2026-09-25)

The document must match an IMF publication (for example an IMF Selected Issues paper or Article IV staff report) in depth of analysis and in presentation.

- Prioritise well-crafted visuals: charts of data, flow charts (for example the model structure, the park-to-port logistics chain, the financing architecture, the value chains) and maps (park sites, the port, the corridors, the Shabelle and Juba valleys, resin and livestock source regions). Every chapter should carry figures where they help the reader; a chapter of text alone needs a reason.
- Every figure is generated by code from the registers and the model outputs (never drawn with typed-in numbers), is listed in data/figures.yaml with the claim and model-output IDs it uses, and carries a source line and, for model outputs, the scenario name ("base scenario, modelled estimate").
- Use IMF conventions: numbered figures, tables and boxes; panel charts with a common style; notes and sources under every figure and table; text boxes for methods and case studies.
- Figure text (Hassan Mumin, 2026-09-25): Times New Roman at 11 point for every text element. tools/figures.py audits each figure before saving it and refuses any figure where text overlaps other text, runs partly off a bar or box, sits in white outside a filled shape, lacks contrast, or sits on a plotted line; every figure is also inspected visually after generation.
- Citations (Hassan Mumin, 2026-09-25): every in-text citation is a numbered footnote at the bottom of the page, and every footnote carries a clickable link to the source (for PDFs, opening at the cited page). A figure's source line carries its own footnote listing the sources behind the figure, with links. This applies to all Parts; tools/build.py produces it.
- The economic model must be fully legible in the document: a model-structure flow chart, the equations in plain notation, the assumption table with sources, the scenario and Monte Carlo ranges, the sensitivity ranking (tornado chart), and a clear statement of what is and is not counted (value added versus sales, import substitution versus GDP, indirect and induced effects reported separately).

## 13. Economic and climate impact model

Build a transparent, bottom-up model in `/model/` (Python, with an Excel export Hassan can inspect). Every input is a verified claim or an approved assumption.

### 13.1 Structure

For each project or product line, by year from 2028 to 2032:

1. **Volume:** throughput or production (tonnes, litres, units, MW), with a ramp-up curve from commissioning to full capacity.
2. **Gross output:** volume multiplied by price.
3. **Value added:** gross output multiplied by a value-added ratio. GDP contribution is value added, never gross output.
4. **Import substitution:** the share of the current import bill displaced, reported as a foreign exchange saving. Keep this separate from value added and do not add the two together.
5. **Export earnings:** additional exports compared with the baseline.
6. **Direct employment:** from plant staffing benchmarks or output per worker.
7. **Indirect and induced effects:** only with a published multiplier from a named study, labelled as such and reported separately from direct effects. (Approved deviation, Hassan Mumin, 2026-09-24: no published multiplier exists for Somalia, so supply-chain value-added coefficients come from IFPRI's published Kenya 2019 and Ethiopia 2022 social accounting matrices, with Somali import leakage; see tools/sam_multipliers.py. Still labelled and reported separately.)
8. **Investment required:** capital cost by project, with the financing source from Part 7.
9. **Fiscal effects:** only where a tax or fee rule is documented.

Aggregate to cluster and national level, and express totals as a share of baseline GDP.

### 13.2 Baseline and scenarios

- Baseline GDP path from the latest official projections (IMF WEO and NBS). Where projections stop before 2032, extend them with a stated growth assumption and label the extension.
- Impacts are measured against a "no policy" baseline, not against zero.
- Three scenarios: low, base and high, varying the key assumptions within their recorded ranges. The report leads with the base scenario and shows the range.
- Run a sensitivity analysis showing which assumptions move the results most.

### 13.3 Double counting and consistency checks

- A byproduct counts once: tallow counts in soap, not in meat; sesame cake counts in feed, not in oil; hides count in tanning.
- Import substitution and value added are reported separately.
- National totals equal the sum of cluster totals.
- Solar mini-grid output is an input cost saving for the clusters, not extra GDP counted again.

### 13.4 Climate impact

For solar mini-grids, solar irrigation, clean cooking, waste methane and electric buses, apply the MCS Technology Analysis Playbook:
- Step 1a: define the incumbent technology and market area; compute CO2 for the incumbent; quantify the service delivered; compute CO2 for the climate solution delivering the same service.
- Step 1b and Step 1: compute technical potential and the implied cost per tonne of CO2, with unit choices stated and caveats listed.
- Step 2: socio-political drivers and barriers, stakeholders, who pays.
- Step 3: potential for speed and scale.

Emission factors come from IPCC defaults or a named methodology, recorded as claims. Report which reductions count toward Somalia's NDC and which could be transferred under Article 6.

### 13.5 Outputs for the report and dashboard

Export a table by project, cluster and year (value added, share of GDP, jobs, investment, import substitution, exports, avoided emissions) to `model/outputs/`, for use in Part 7, in the Part 2 targets, and later in the Part 2 dashboard scenario tool.

## 14. Working rhythm

- Work in phases and stop at each checkpoint for Hassan's approval.
- Keep a running `reports/progress.md`: what was done, what is blocked, what needs Hassan.
- Never delete a source file or a claim. Mark superseded claims `status: superseded` with a pointer to the replacement.
- When unsure, ask. A question costs less than a wrong figure in front of the President.
