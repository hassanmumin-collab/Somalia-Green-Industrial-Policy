# Checkpoint 2: claims extraction and verification

Prepared for Hassan Mumin on 23 September 2026. Three items are presented for approval: the verification result, the conflicts between sources, and the figures the report needs that no source supports.

## 1. Verification result

`verify.py --all` passes with 0 failures and 0 warnings. The full output is in `reports/verification_report.md`.

| Item | Count |
|---|---|
| Claims in the register | 234 |
| Source claims | 229 |
| Derived claims (2024 import totals, recomputed by the verifier) | 5 |
| Claims passed by the independent fact-checker | 234 |
| Claims corrected after a fact-check fail or query, then re-checked | 28 |
| Sources cited by claims | 43 |
| Claims resting on Tier 1 sources | 134 |
| Claims resting on Tier 2 sources | 68 |
| Claims resting on Tier 3 sources | 24 |
| Claims resting on Tier 4 sources | 3 |

By basis, 112 claims are actuals, 66 estimates, 27 projections and 24 targets. The chapters must label each accordingly, and the verifier enforces this.

### What the fact-check changed

The independent fact-checker ran in eight batches plus three re-check rounds. Verdict files are in `reports/factcheck/`. The substantive corrections were:

- **Livestock exports.** The Central Bank's values and head counts are FAO-FSNAU and Central Bank valuations. They are now labelled estimates, not actuals.
- **The USD 823 million livestock figure.** It is livestock exports in real terms from the national accounts, not an error. Conflict X-005 is therefore resolved.
- **Electricity access (World Bank, 2025).** The 71 percent is access at Tier 1 or above, meaning at least four hours a day, from preliminary survey results. It is not "any access", which the same report puts at about three-quarters.
- **Emissions.** The 54.3 MtCO2e figure for 2024 is a provisional estimate that includes land use.
- **Scope wording.** Several statements were narrowed so they say no more than their source. For example, the 2.8 percent of GDP is federal government revenue, the FSNAU price rise applies to shilling-using areas, and Kenya's 36,000 covers the whole business services workforce.
- **Somali legal texts.** Law numbers and dates for the Environment, Electricity, Fisheries, Standards and Investment laws and the Industrial Policy decree were confirmed against the page images. The investment law is Law No. 011. The industrial policy decree was signed by the Deputy Prime Minister.

### Verifier changes made during Phase 2

Each change has a test, and all 94 tests pass.

- **CSV and zip sources.** In CSV and zip sources, commas are read as field separators.
- **Numeric tolerance.** Tightened from one part in a billion to one part in a trillion. A test showed the old tolerance accepted a wrong 11-digit value.
- **Glued units.** Numbers with glued units ("200,000ha", "5MW") and capitalised scale words ("36K", "USD 8Bn") are now read correctly.
- **Hyphen ranges.** A hyphen between two numbers ("17%-59%") is read as a range, not a minus sign.
- **`quote_context`.** A new optional field lets a table row carry its column header, for example "Country fNRB (%)". The header must appear on the same page.
- **OCR warnings.** These are now limited to claims on OCR'd pages.

## 2. Conflicts between sources

Full entries are in `data/conflicts.yaml`. "Proposed" resolutions need your approval.

| ID | Measure | Resolution |
|---|---|---|
| X-001 | GDP at current prices, 2025 | Proposed: use NBS (USD 13,234 million); show the IMF estimate (USD 12.956 billion, September 2025 data vintage) alongside it |
| X-002 | Real GDP growth, 2025 | Proposed: use NBS (3.1 percent); note the IMF estimate (3 percent) |
| X-003 | Livestock exports, 2018 | Re-estimate: use the Central Bank's later figure (USD 311.1 million, your lead), with its origin stated |
| X-004 | Livestock exports, 2024 | Revision: use USD 950.9 million, not the earlier USD 969.9 million (your USD 970 million lead) |
| X-005 | Livestock exports, 2025 | Resolved: USD 922.9 million nominal and USD 823 million real are both correct |
| X-006 | Livestock exports, 2024 (Central Bank against FAOSTAT) | Proposed: use the Central Bank (USD 950.9 million). FAOSTAT (USD 414.1 million) relies on partner-country data and misses Gulf trade |
| X-007 | Renewable share of electricity | Proposed: state both (NDC 12 percent of installed capacity; World Bank 20 percent, basis not stated) |
| X-008 | Sesame 2024 | FAOSTAT exports exceed its own production figure; use only as an order of magnitude |
| X-009 | Sesame production | Needs a Ministry of Agriculture figure. FAOSTAT gives 16,543 tonnes; FAO's investment case uses about 50,000 tons, possibly for its programme area only |
| X-010 | Potential fish harvest | Proposed: state the range (380,000 to 835,000 tonnes); plan on the lower, more recent estimate |
| X-011 | Cookstove target | Proposed: NDC 3.0 (1,178,000 by 2035) is the current plan; the 5 million figure is an earlier ambition |
| X-012 | Current fish catch | Proposed: use the World Bank estimate of 50,000 tonnes domestic catch; the NTP's 120,000 tonnes baseline may include foreign catch |
| X-013 | Population | **Your decision.** The 2014 official estimate is 12.3 million; NDC 3.0 uses 19.6 million; there has been no census |
| X-014 | Generation plan costs, 2030 to 2050 | The plan's text (USD 22.9 billion) disagrees with its own table (USD 23.6 billion); state both if used |

## 3. Figures the report needs that no source supports

These are listed by Part in `reports/figure_gaps.md`. The main gaps are:

- **Plant cost benchmarks.** Capacity, staffing, capital cost and value-added ratio are missing for most product lines. Only sesame oil has a capital cost, and Kenya BPO has employment and labour-cost comparators. Soap, diapers, tanning and garments have nothing usable.
- **Mogadishu.** No waste, sewerage, flood-damage, bus or population data.
- **Carbon credit prices** for cookstoves, landfill gas and Article 6 transfers.
- **National poverty rate.**
- **Diesel generation cost per kWh.** This can be derived from sourced inputs, but needs your approval as a derived claim.
- **UN Comtrade import data.** The partner-country pull by HS code would fill several import gaps (soap, detergents, diapers, edible oils). It has not been run yet.

## 4. Decisions requested

1. Approve or amend the proposed resolutions in section 2, and decide X-013 (population).
2. Choose, for the plant-benchmark gaps, between two options. One is a focused further search before Phase 3. The other is a model that uses stated comparator assumptions with wide ranges, for your approval in `data/assumptions.yaml`.
3. Confirm I should run the UN Comtrade partner-country pull before Phase 3.
4. Approve deriving the diesel generation cost per kWh from the sourced fuel price and heat-rate claims.
