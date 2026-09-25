# Checkpoint 3 (revised): impact model and assumptions

Prepared for Hassan Mumin on 24 September 2026. This version replaces the first Checkpoint 3 package. It responds to your comments:

- GDP impact looked too low.
- The wider economic benefits were missing.
- Meat should focus on camel and cattle meat for premium markets.
- The fish sector was not visible.
- The IFPRI matrices and the World Bank light-manufacturing study had been supplied.

The verifier passes, all 98 tool tests and 15 model tests pass, and the model reruns in one command. **91 new claims have not yet had the independent fact-check** (C-0337 to C-0412 and D-0044 to D-0058). The checking agent stopped when the account reached its monthly spend limit. No figure from those claims may enter a chapter until they pass.

Files to open:

- `model/outputs/gip_model.xlsx`: every assumption, results by line and year, the Monte Carlo band and the sensitivity ranking.
- `data/assumptions.yaml`: 170 assumptions, with the rationale for each.
- `reports/sam_multipliers.md`: the multiplier analysis from the IFPRI matrices.

## 1. Why the first GDP figure was small, and what changed

Your instinct was right that 0.13 percent understated the policy, for two reasons.

- **Scale.** The first proposal sized the plants cautiously, at about USD 190 million of gross output in 2032, inside a projected GDP of USD 24.4 billion. The capacities are now tied to documented markets and plan targets:
  - Fish processing aims at 40 percent of the NTP's 146,732-tonne programme.
  - Flour mills replace 60 percent of flour imports.
  - Meat plants take about 6 percent of the Gulf's chilled beef imports.
  - Garments reach 10,000 sewing jobs.
  - BPO reaches 5,000 seats.
- **Scope.** The first model counted only the plants' own value added. It now also counts the value added the plants create upstream among herders, fishers, farmers, traders and transporters (indirect). It also counts what households add to GDP when they spend the extra income (induced). This is the standard method IMF and World Bank analysts use: the value-added content of supply chains from the IFPRI matrices for Kenya and Ethiopia, combined with Somalia's own import leakage.

One point needs to be stated plainly in the policy. GDP counts value added, not sales. The plants' output in 2032 is USD 324 million, but value added is only the part left after paying for inputs. Reaching 1 percent of GDP from the plants alone would require about USD 1.2 billion of new output a year. The 2028 to 2032 period builds the first plants. The larger gains come as the clusters mature after 2032.

**Revised results, base case, 2032** (illustrative scenario results, not forecasts; USD million unless stated):

| Measure | Low | Base | High | Monte Carlo P10 to P90 |
|---|---|---|---|---|
| Gross output of the new plants | 53 | 324 | 1,328 | |
| Direct value added | 9.5 | 78.0 | 409.5 | 70.6 to 105.5 |
| Total value added (direct, indirect and induced) | 14.8 | 176.5 | 1,347.6 | 149.0 to 242.3 |
| Total value added as share of GDP | 0.06% | 0.72% | 5.53% | 0.62% to 1.00% |
| Direct jobs | 4,194 | 17,073 | 48,980 | 14,345 to 22,992 |
| Household income | 6.7 | 105.9 | 1,010.7 | 85.1 to 150.7 |
| Net foreign-exchange effect | 22.2 | 216.5 | 1,082.8 | 186.6 to 294.3 |
| Avoided emissions (t CO2e) | 39,485 | 326,651 | 1,108,469 | 229,418 to 412,782 |

How to read the columns:

- **Low and high.** These push all 170 assumptions to one end of their ranges at once. They are stress tests, not likely outcomes.
- **Monte Carlo.** The Monte Carlo draws 2,000 random combinations within the ranges and shows the band holding 80 percent of the results. It is the better guide to the realistic range, and the policy should lead with it and the base case.
- **Growth.** In the base case, the programme adds about 0.2 percentage points a year to GDP growth from 2029 to 2032. Total value added rises from USD 14.7 million in 2028 to USD 176.5 million in 2032, and direct jobs from 2,561 to 17,073.

## 2. The other economic benefits you asked for

**Foreign exchange.** The plants replace USD 156.4 million of imports and earn USD 167.2 million of exports in 2032. After imported inputs and the raw exports they absorb, the net gain is USD 216.5 million in 2032 and USD 577.3 million over 2028 to 2032. Building the plants imports USD 213.3 million of machinery over the same years, so the programme pays back its own foreign-exchange cost within the period. These dollars stay in the Somali economy, but GDP already counts the local production behind them. The report presents the foreign-exchange gain as a balance-of-payments and resilience benefit, never added to GDP.

**Household purchasing power.** Households receive an estimated USD 105.9 million of income in 2032 from wages, herders' and fishers' sales, and profits that stay in Somalia. The model assumes 30 percent of their spending buys Somali goods and services, which is where the induced effect comes from. Somalia's heavy import dependence (C-0038) is why the induced effect is modest at USD 22.9 million. A stronger local supply of food and services would raise it.

**Tax base.** This finding needs your attention. At Somalia's current average revenue effort of 2.8 percent of GDP (C-0222), the new activity yields about USD 4.9 million of revenue in 2032. The customs duty lost on the imports it replaces is about USD 7.8 million, at an assumed 5 percent effective duty rate that is not yet sourced. The tax base grows, but federal revenue falls unless the policy acts. Two measures would fix this:

- Firms in the industrial parks are formal, registered and easy to tax, so their revenue per dollar of value added should be well above the national average.
- A sales tax or excise applied to domestic production would replace the customs duty lost on displaced imports.

I recommend the policy states this explicitly. It is the kind of point finance ministries and the IMF will check.

## 3. Meat: chilled beef and camel meat for the Gulf

The trade data support your direction:

- **The chilled market is large.** The six GCC states imported USD 1,094.9 million of fresh or chilled beef in 2023 (D-0053), at USD 6.99 per kg (D-0054).
- **Chilled earns a premium.** It sells for 42 percent more than frozen beef, which averaged USD 4.92 per kg (D-0055, D-0058). That chilled premium is the prize for a Mogadishu plant close to Gulf markets.
- **Live trade is small, so the risk is low.** Oman reported only about 31,000 live cattle from Somalia in 2023 (C-0408). The plants can buy cattle and camels now sold in domestic markets without cutting into live exports.
- **Sheep and goats are different.** A live animal earns more per kg than meat (D-0040), so they are left to the live trade.
- **Camel meat is a niche, not a volume market.** Gulf imports of "other meat", which includes camel, were only about USD 15 million.

The meat line is now "chilled beef and camel meat": 15,000 tonnes of capacity, priced at 90 percent of the Gulf chilled price. In the base case it exports USD 45.9 million in 2032 and generates USD 25.4 million of total value added. The Gulf joint venture's certification and supply security remain the value proposition.

## 4. Fish

Fish was in Cluster 1 from the start but was sized too small to stand out. It is now the largest single line:

- **Scale.** Processing capacity is 60,000 tonnes by 2032, about 40 percent of the NTP's downstream processing programme (C-0260). The plan's own cost and jobs ratios apply: USD 673 of investment and 38 jobs per 1,000 tonnes (D-0041, D-0042).
- **Base-case results, 2032.** The line produces USD 57.6 million of total value added, 1,824 direct jobs and USD 70.0 million of net foreign exchange.
- **The binding condition is landings.** Somali fishers land an estimated 50,000 tonnes a year (C-0153), while foreign vessels take about 100,000 tonnes (C-0154). The policy needs fisheries licensing and surveillance to bring more of the catch ashore in Somalia.

Fish is also the assumption that moves results most. The model can quantify processing, but the fish must be landed first.

## 5. The World Bank's light-manufacturing study

The study (S-149, 2012) covers Ethiopia, Tanzania and Zambia, not Somalia, so the policy will use it as regional evidence:

- **Wages and productivity.** African light manufacturing can compete. Well-managed Ethiopian firms approached Chinese and Vietnamese productivity at a quarter of China's wages (C-0374).
- **Siting.** Industrial parks succeed when they build on local comparative advantage (C-0375). That supports the choice of livestock, fish and sesame for the clusters.
- **Plug-and-play parks.** Such parks cut production costs by about 2 percent in the study's example (C-0376).

## 6. The data search you asked about

**Solar resource at the park sites: found.**
- The World Bank's Global Solar Atlas gives Mogadishu 1,785 kWh per kW of panels a year (C-0377), a capacity factor of 0.204 (D-0052).
- This replaces my judgment of 0.20.

**Mogadishu waste tonnage: partly found.**
- A 2026 peer-reviewed study cites about 2,500 tonnes a day for Mogadishu (C-0378), with UN-Habitat's 2012 estimate of 1,500 tonnes a day for all urban Somalia as a conflict (X-018).
- Somalia's Biennial Update Report assumes 25 percent of urban waste is collected (C-0381).
- The landfill module now takes 230,000 tonnes a year, about that collected share. No measured tonnage exists.

**Diesel irrigation pumps: not found.**
- No count of pumps or their fuel use exists in any source I could reach. The World Bank's riverine assessment (S-151) has none.
- The Ministry of Agriculture and Irrigation or FAO SWALIM are the likely holders. This remains a judgment input.

**Charcoal prices in Mogadishu: need your action.**
- FSNAU publishes weekly market prices, which probably include charcoal, but its data service requires a registered access key.
- You could request one at https://api.fsnau.org/users/request_api_access. Until then the price stays a judgment.

## 7. Decisions requested

1. **Approve or amend the 170 assumptions.** The capacities are the main lever. The base case now gives total value added of 0.72 percent of GDP in 2032 (0.62 to 1.00 percent in the Monte Carlo band) and about 17,000 direct jobs. The biggest movers are fish capacity and price, the value-added content of supply chains, additionality, BPO seats, meat capacity and garment jobs.
2. **Approve the multiplier method.** CLAUDE.md section 13.1 allows indirect and induced effects only "with a published multiplier from a named study". No published multiplier exists for Somalia. I derived the supply-chain coefficients from IFPRI's published Kenya and Ethiopia matrices and set the household leakage from Somalia's import dependence, so this is a documented deviation from the rule that needs your approval. Indirect and induced effects are always reported separately from direct value added.
3. **Approve the fiscal framing.** Report gross new revenue and customs lost separately, and add the tax-design recommendation in section 2.
4. **Approve conflict X-018** (waste tonnage). I resolved X-015 to X-017 under your delegation, adopting the proposed resolutions.
5. **Charcoal prices, if you want them.** Request an FSNAU data key, or point me to anyone at the Ministry of Agriculture with pump data.

After your approval, and once the fact-checker has run on the 91 pending claims, I will register the model outputs the report uses and start Phase 4 with Part 1.
