# Project organization

`README.md` is the entry point. `reports/NEXT_STEPS.md` records completed work and
the outstanding case-study inputs. The original handoff is preserved verbatim in
`rooftops_repowered_v2_1_context.txt`; the V2.2 handover and explicit user decisions
configuration supersede its older artifact paths and pending statuses.

```text
config/
  project.json                    # paths, selected demand route, A160 host identity
  roof_capacity.json              # current-geometry gates and capacity assumptions
  a160_assessments.json           # active retrospective/additional roof protocol
  a160_pv_reference_annotation.json # manual image reference and B-only masks
  simulation.json                 # office operation grid, weather-year convention
  impact_assumptions.json          # intentionally unset sourced costs/carbon
  experiments/                    # initial benchmark protocol and excluded test IDs
pipeline/
  __main__.py                     # command-line entry point
  common.py, temporal.py          # shared validation/config/time helpers
  step_01_data_audit/             # source scans and quality reports
  step_02_roof_capacity/          # V1-derived geometry, masks, packing and QA gates
  step_03_pvgis/                  # generation import, no new PV physics
  step_04_demand_preparation/     # measured cohort, features, train/validation/test
  step_05_demand_baseline_hour_of_week/ # reference estimator
  step_05_demand_baseline_seasonal/     # reference estimator
  step_05_demand_xgboost/         # measured-data benchmark and inference
  step_05_simulation_surrogate/   # EnergyPlus setup, scenarios, training, inference
  step_06_scenarios/              # explicitly synthetic schedule adjustments
  step_07_energy_balance/         # PV/demand/share conservation
  step_08_impact_metrics/         # sourced cost/carbon/benefit screening
  models/                         # every trained artifact and model manifest
datasets/
  raw/                            # original data, cadastral geometry, IWEC weather
  processed/                      # derived training tables and future case series
  inputs/                         # identified candidates plus unfilled geometric inputs
  synthetic/energyplus/            # per-scenario physical inputs, outputs and logs
  results/                        # benchmark metrics and held-out predictions
reports/
  data_audit/                     # source/column quality and preparation evidence
  demand_model/                   # measured-data results; initial experiment archive
  simulation_surrogate/           # physics setup, splits, evidence and model card
  roof_capacity/A160/             # two assessments, source evidence, figures/report
  integration/                    # folder migration and V1 port evidence
docs/                             # methods and input/output contracts
tests/                            # focused correctness checks
tools/energyplus/                  # portable official engine and reference examples
```

No trained model is stored inside `datasets/`. Large local inputs, derived training
tables, simulator output directories and model binaries are ignored by Git;
configuration, source code and compact evidence remain reviewable. No Git commit
or deployment is performed by this setup.

Numbers specify execution stages; all step 05 folders belong to the same model
stage. `pipeline/models/` is deliberately preserved as the artifact location.
V1 sources are copied, attributed and adapted in step 02; V1 itself is unchanged.

`datasets/inputs/roof_capacity/` contains A160's real footprint, independent image
reference, current occupancy/access masks and separate PVGIS handoffs.
`datasets/processed/roof_capacity/A160/{retrospective,additional}/` keeps the two
assessment outputs separate. The disposable Chicago-reference inference CSVs and
check were removed; legitimate demand-surrogate training references remain.
