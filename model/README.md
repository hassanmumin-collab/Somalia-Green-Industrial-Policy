# Economic and climate impact model

Built in Phase 3 to CLAUDE.md section 13. Contract the verifier relies on:

- `model/engine.py` exposes `compute(scenario, root)` returning
  `{output_key: {"value": float, "depends": [assumption ids]}}` for scenario `low`, `base` or `high`.
- `model/inputs.yaml` lists every model input as `{name, ref}` where `ref` is a verified claim (C-/D-) or an assumption (A-).
- No numeric literals other than 0 and 1 in model code. Structural constants (for example the policy years) carry `# allow-literal: <reason>` on the same line.
- Model outputs used in the report are registered as M- claims in `data/claims.yaml` with `output_key`, `scenario`, `value`, `unit`, `rounding` and status `illustrative`.

## Running the model

```
.venv/Scripts/python.exe model/run.py                              # scenarios, checks, sensitivity, CSV and Excel exports
.venv/Scripts/python.exe -m unittest discover -s model/tests -t .  # accounting-rule tests
```

Outputs go to `model/outputs/`: `results_long.csv` (every line, cluster, national and climate metric by scenario and year),
`outputs_flat.csv` (the `compute()` keys with their assumption dependencies), `checks_base.csv`, `sensitivity.csv` and
`gip_model.xlsx` (the same tables for review in Excel). Inputs carry a `direction` in `inputs.yaml`: `up` means a higher
value raises the policy's net benefits, so the high scenario takes the top of the range; `down` the reverse; `none` is not
varied across scenarios (sensitivity still moves it).

## Optional line inputs (added 2026-09-24)

A product line may list two optional inputs in `model/inputs.yaml`:

- `<line>.additionality` replaces the cluster's additionality for that line. Stoves and pellets use it: some efficient stoves would be imported anyway, and pellets largely replace domestic charcoal.
- `<line>.import_displacement` is the share of domestic sales that replaces imports (default 1). Pellets use 0 because they replace domestic charcoal; dairy and fruit use less than 1 because part of their home sales replaces local products.

Clean cooking is modelled from the Cluster 3 stove and pellet lines. The cooking climate module counts the additional stoves in use (sales over the stove's life) and the charcoal the pellets replace. It reports household fuel savings (`climate.cooking.household_saving.<year>`) and the subsidy needed to bring the stove price down to an affordable level (`climate.cooking.subsidy.<year>`). Neither is added to value added.
