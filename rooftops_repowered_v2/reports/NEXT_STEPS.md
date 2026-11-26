# Project progress and next steps

## Existing PV / official PVGIS integration (15 November 2026)

Priorities 1–2 now include a direct image-reference vs predicted-layout comparison
and an official PVGIS hourly sensitivity explorer. Automatic acquisition produced
five positive hypothetical scenarios from four cached responses, 8,760 rows each;
zero capacity skips simulation. Actual installed PV specifications/generation stay
unknown. All hypothetical supply remains sharing-ineligible. See
[results and verification](../ui/docs/pv-integration/README.md) and
[automatic/manual acquisition](../pipeline/step_03_pvgis/README.md).
Stitch authentication, private project creation and approved HTML-reference upload
are verified. The next substantive phase is site-appropriate demand preparation
and independent sharing evaluation, with its geometry/weather/data gates intact.

## Read-only UI integration (15 November 2026)

The approved seven-view prototype is connected to real A160 roof/reference and
office-model reports. Run `python -m ui.server`; see [UI instructions](../ui/README.md)
and [test/screenshots report](../ui/docs/IMPLEMENTATION_REPORT.md). Existing models,
scientific outputs and validation gates are unchanged. Energy/impact stages stay
pending for the actual case. The subsequent PV integration above supersedes the
initial acquisition status; hypothetical modeled generation is now available.

## A160 rooftop milestone (2026-11-15)

Completed provisional dual assessment: retrospective geometric potential
95.34 / 110.88 / 116.76 kWp; conditional additional capacity 0 / 1.26 / 1.26 kWp.
All are low confidence. Existing installed capacity is unknown. The finalized
2025 orthophoto supplies the quantitative reference; newest provisional imagery
from 2026-03-16 supplies visual context. LiDAR acquisition is 2022-06-01 and
already includes PV; municipal comparison records are legacy 2015 geometry.
See [the full report](roof_capacity/A160/README.md), including the low spatial
agreement and source limitations. Run `python -m pipeline roof-feasibility`.
V1 code is integrated, numbered folders are in place and all trained models are
preserved under `pipeline/models/`. No demand retraining occurred.

## Completed foundation

- Downloaded and structurally audited all eight core datasets plus Barcelona
  cadastral geometry. Full field-level missingness and meter ranges are in
  `reports/data_audit/column_quality.csv`.
- The Barcelona 2025 consumption export covers January–November only. Certificates
  are modeled energy-performance records, not measured consumption.
- Prepared a 70-building pilot and a 310-building expanded BDG2 cohort. The expanded
  table has 5,258,034 retained measured hourly readings.
- Trained two baselines and XGBoost, with disjoint buildings and reproducible inputs.
  Both measured-data XGBoost experiments failed the primary MAE gate. No local
  Barcelona accuracy is claimed. The initial experiment is archived separately.
- Implemented PVGIS import, UTC alignment, explicit schedule adjustment, share-plan
  generation, four energy scenarios and sourced impact-screening code.
- Added host-free configuration and empty case-study templates. Every trained model
  belongs under `pipeline/models/`.

## Office physics route

The user selected this route after the measured-data experiment, starting with
office archetypes only. Portable EnergyPlus and Barcelona IWEC reference weather
are available locally. An annual office smoke simulation succeeded. The full grid
contains 36 completed operating configurations (315,360 simulated hourly targets).
The surrogate passed both validation and test comparisons against the hourly and
schedule-aware linear baselines. Test MAE is 0.648 kWh/hour versus 1.465 for the
linear baseline and 2.335 for the hourly baseline. Test NMAE is 11.96% of mean
simulated demand. The partitions contain 22 training, 7 validation and 7 test
configurations; none shares a configuration with another partition.

The model and its manifest are saved in `pipeline/models/`. Both
`reports/simulation_surrogate/MODEL_CARD.md` and `readiness.json` record the outcome.
The generic `predict` command now uses this configured office-surrogate route;
`predict-bdg2` retains the measured-data benchmark. Saved-model CLI inference was
checked on 168 synthetic reference hours against direct model predictions.

Simulation validation excludes entire operation configurations. Its geometry,
HVAC and envelope are one published U.S. office reference, with Barcelona weather
and design days. Results describe simulator approximation, not measured local
building behavior. New geometry and other uses require domain expansion.

## Deferred beyond the rooftop milestone

1. Confirm the identified participant buildings, functions, floor areas and sources.
2. Verify existing PV specifications and the small additional candidates against
   roof/access plans; choose PVGIS weather/losses and export the appropriate
   separate hourly series. Never treat retrospective potential as actual existing PV.
3. Explicit representative-year/calendar convention and sourced hourly weather;
   inspect PVGIS minute offsets before joining to demand.
4. Evidence-backed archetype/operation parameters for the selected buildings. The
   office surrogate cannot silently scale one reference geometry to arbitrary areas.
5. Independently held-out demand references for testing allocation value; do not
   score a forecast-derived plan against that same forecast and call it validation.
6. Dated tariffs, PV capex/O&M, emissions year/boundary and cost/benefit-sharing choices.
7. Legal eligibility/settlement verification before making compliance claims.

The next practical steps are to review the rooftop assumptions and obtain existing
installation/access details, then select PVGIS settings. Before demand work resumes,
review the office surrogate's domain and expand geometry/operation ranges before
applying it to actual buildings.
Interface work follows those results; no citywide or live-control functionality is planned.
