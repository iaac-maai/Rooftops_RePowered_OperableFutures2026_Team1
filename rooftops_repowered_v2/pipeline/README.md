# Step-by-step execution

| Step | Folder | Purpose / command |
| --- | --- | --- |
| 01 | `step_01_data_audit/` | Source audit: `python -m pipeline audit` |
| 02 | `step_02_roof_capacity/` | A160 dual rooftop assessment: `python -m pipeline roof-feasibility` |
| 03 | `step_03_pvgis/` | Roof-specific generation: `python -m pipeline import-pvgis ...` |
| 04 | `step_04_demand_preparation/` | Measured benchmark cohort: `python -m pipeline prepare` |
| 05 | `step_05_demand_baseline_hour_of_week/` | Hour-of-week reference estimator |
| 05 | `step_05_demand_baseline_seasonal/` | Seasonal reference estimator |
| 05 | `step_05_demand_xgboost/` | Measured-data benchmark: `python -m pipeline train` |
| 05 | `step_05_simulation_surrogate/` | Active office route: `python -m pipeline train-office-surrogate` |
| 06 | `step_06_scenarios/` | Explicit operating scenarios |
| 07 | `step_07_energy_balance/` | Pre-agreed shares and balances: `plan-shares`, `match` |
| 08 | `step_08_impact_metrics/` | Sourced financial/carbon/benefit screening: `impacts` |

Step 05 folders are alternatives/benchmarks in the same model-development stage,
not four models that must all drive the case study. Demand development can run
independently while roof/PVGIS inputs for steps 02–03 are collected.

`models/` remains unnumbered because it stores artifacts rather than executing a
step. **All trained artifacts remain in `pipeline/models/`.** Old baseline
pickles still load through a lazy compatibility alias; no model was retrained or
rewritten merely to rename a folder. Shared config/time/validation helpers remain
at package root.

A160's footprint is identified and existing PV is confirmed. Step 02 separates
retrospective potential from current additional capacity. Both remain low-confidence
screening; installed specifications and electrical eligibility are unverified.
See [the milestone report](../reports/roof_capacity/A160/README.md). It does not
execute demand training or complete the downstream energy-community pipeline.

See [roof-capacity instructions](step_02_roof_capacity/README.md),
[project structure](../docs/PROJECT_STRUCTURE.md) and `python -m pipeline --help`.
