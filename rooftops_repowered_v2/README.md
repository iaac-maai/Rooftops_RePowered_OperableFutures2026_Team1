# Rooftops RePowered V2

AI-assisted rooftop solar and building-electricity matching for a small Barcelona
cluster. This is a reproducible planning and validation research prototype. The real
host is A160 (Almogàvers 160); the identified mixed-use participants are ITAEB,
Ciutat de Granada 95–97 housing and NH Diagonal Poblenou. Rooftop screening is provisional; operating assumptions
and electrical eligibility still need verification.

Start with [current progress and next steps](reports/NEXT_STEPS.md),
[the implementation pipeline](PIPELINE.md), [method and limitations](docs/METHOD.md)
and [input contracts](docs/DATA_CONTRACTS.md).

The **A160 rooftop feasibility milestone is complete as provisional screening**.
See [the results and limitations](reports/roof_capacity/A160/README.md) and
[annotated rooftop figure](reports/roof_capacity/A160/A160_two_assessments.png).
Existing PV is confirmed; retrospective potential and additional capacity have
separate outputs. The working demand surrogate is unchanged.

The approved seven-view UI is integrated as a local read-only dashboard. Launch
with `.\.venv\Scripts\python.exe -m ui.server`, then open `http://127.0.0.1:8765`.
See [UI instructions](ui/README.md), [implementation/screenshots](ui/docs/IMPLEMENTATION_REPORT.md)
and [persistent Google Stitch setup](ui/integrations/README.md).

The tool now compares existing image-derived PV coverage with our roof layouts
and displays separately tagged official PVGIS hypothetical hourly generation.
Acquire/cache data with `.\.venv\Scripts\python.exe -m pipeline pvgis-acquire`.
Actual installed specifications remain unknown. See [PV workflow and results](ui/docs/pv-integration/README.md).

## Run locally

Use the project's existing Python environment from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pipeline status
.\.venv\Scripts\python.exe -m pipeline --help
```

For a fresh Python environment, install `requirements-lock.txt` for the exact
tested versions, or `requirements-dev.txt` for compatible runtime/test dependencies.
The current environment is Python 3.14.5 on Windows. Normal processing is offline
after downloading source data and the optional simulator.

## Data and measured-demand benchmark

```powershell
.\.venv\Scripts\python.exe -m pipeline audit
.\.venv\Scripts\python.exe -m pipeline prepare
.\.venv\Scripts\python.exe -m pipeline train
```

The first two BDG2 XGBoost experiments failed to beat the hour-of-week baseline
on primary validation MAE. Their evidence is retained; the baseline remains the
recommended estimator for this measured-data route. See
[the generated benchmark model card](reports/demand_model/MODEL_CARD.md).
International reference readings are not Barcelona meters, and building-opening
hours are not observed electricity.

## Office simulation-surrogate route

After the measured-data benchmark, the agreed next AI route is EnergyPlus-derived
office demand with explicitly controlled operating scenarios:

```powershell
.\.venv\Scripts\python.exe -m pipeline.step_05_simulation_surrogate.setup
.\.venv\Scripts\python.exe -m pipeline.step_05_simulation_surrogate.simulate
.\.venv\Scripts\python.exe -m pipeline train-office-surrogate
```

The portable engine is isolated in `tools/energyplus/`; no system installation
or PATH change is required. The initial 36 configurations use one official office
reference model with Barcelona IWEC weather. They are not real local measurements.
See [the simulation workflow](pipeline/step_05_simulation_surrogate/README.md) and
[the simulation model card](reports/simulation_surrogate/MODEL_CARD.md).
Any AI gain here means improved approximation of the simulator within its tested
domain, not verified prediction of the eventual selected building.

## A160 rooftop milestone and later case-study connection

The folders now follow `step_NN_name` execution order. See
[the stage index](pipeline/README.md). V1 roof extraction and panel packing are
integrated in [step 02](pipeline/step_02_roof_capacity/README.md):

```powershell
.\.venv\Scripts\python.exe -m pipeline roof-feasibility
```

This offline command regenerates the two assessments from cached real A160 data,
retaining the frozen retrospective prediction unless explicitly rebuilt. Current
additional capacity is conditional; observed installed kWp remains unknown.
`roof-capacity` and `roof-pvgis-settings` remain generic strict workflows for a
future reviewed geometry case; A160 uses `config/a160_assessments.json` instead.

1. Fill the building/roof templates under `datasets/inputs/`, retaining sources.
2. Review the A160 identity in `config/project.json` and assumptions/annotations
   in `config/a160_assessments.json` and `config/a160_pv_reference_annotation.json`.
3. Select the appropriate separate PVGIS handoff under `datasets/inputs/roof_capacity/pvgis/`;
   verify design/capacity and choose weather period/losses before generation import.
4. Supply sourced hourly weather/building inputs and select a model supported by
   those buildings. The office surrogate deliberately rejects arbitrary geometry
   scaling; add the new geometry to its simulation domain first.
5. Generate and freeze a hypothetical share plan, evaluate it against independent
   demand references, then add sourced impact assumptions.

```powershell
.\.venv\Scripts\python.exe -m pipeline predict --input YOUR_CONFIGURED_MODEL_FEATURE_FILE.csv
.\.venv\Scripts\python.exe -m pipeline predict-bdg2 --input YOUR_BDG2_FEATURE_FILE.csv
.\.venv\Scripts\python.exe -m pipeline predict-office --input YOUR_OFFICE_SURROGATE_FEATURE_FILE.csv
.\.venv\Scripts\python.exe -m pipeline import-pvgis --input YOUR_EXPORT.csv --settings YOUR_SETTINGS.json
.\.venv\Scripts\python.exe -m pipeline plan-shares --input YOUR_FORECASTS.csv
.\.venv\Scripts\python.exe -m pipeline match
.\.venv\Scripts\python.exe -m pipeline impacts
```

`match` and `impacts` stop with an actionable message until real case-study inputs
exist. Costs/emissions factors are unset. No example building, tariff or apparent
environmental benefit is substituted for missing information.

## Find files

| Folder | Contents |
| --- | --- |
| `config/` | Project paths, A160 roof/case-study inputs, experiment and simulation settings |
| `pipeline/` | Organized processing, model and accounting modules |
| `pipeline/models/` | All trained artifacts, schemas and manifests |
| `datasets/raw/` | Original downloaded publisher data |
| `datasets/processed/` | Audited/prepared training and future case-study series |
| `datasets/synthetic/` | Explicit schedules, EnergyPlus inputs and simulation outputs |
| `datasets/results/` | Model metrics, held-out predictions and later energy comparisons |
| `reports/` | Audits, benchmark evidence, model cards and next steps |
| `docs/` | Data contracts and research method |
| `tests/` | Energy conservation, time handling, provenance and leakage checks |
| `tools/` | Local portable simulator; excluded from Git |

Large raw data, fitted binaries and derived training tables remain local; source
code, configuration and compact reports remain reviewable. There is no deployed
site or real-time energy controller.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover conservation, the no-extra-benefit case when the host already consumes
all PV, invalid coefficients, UTC/DST handling, source hour-end conversion, building
split leakage, unsupported use/geometry rejection and missing impact assumptions.
