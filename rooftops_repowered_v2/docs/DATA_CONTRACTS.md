# Input and output contracts

## Existing PV and hypothetical PVGIS

`config/a160_existing_pv.json` explicitly keeps actual installed capacity, module
count/Wp, tilt/orientation and inverter details unknown. Image identity/coverage
do not populate those fields. `config/pvgis_hypothetical.json` separately defines
explicit sensitivity assumptions; automatic `seriescalc` acquisition reuses the
existing importer and temporal validation. See [step 03](../pipeline/step_03_pvgis/README.md).

Hypothetical normalized series are stored under
`datasets/processed/pvgis/A160/hypothetical/`, with `data_origin=SIMULATED_PHYSICS`,
scenario/model/role metadata, `hypothetical=true` and `energy_sharing_eligible=false`.
Original UTC minute offsets are retained. The actual case-study supply path is
not written. Case-study `match` rejects explicit hypothetical/false-eligibility
flags even if a user manually repoints its PV path. Actual generation remains null.

## A160 dual rooftop milestone

`config/a160_assessments.json` is the active rooftop protocol. The retrospective
predictor consumes cadastral footprint, classified LiDAR points and structural/
module/scenario parameters only. Image-reference PV coverage is a scoring target;
current array envelopes, roof boundary and access/plant masks are additional-
feasibility inputs only. GeoJSON is WGS84; geometry calculations use EPSG:25831.

`datasets/processed/roof_capacity/A160/{retrospective,additional}/roof_capacity_scenarios.csv`
contains separate conservative/base/optimistic rows. `panel_count` and
`estimated_kwp` describe assumed new modules, not observed installed specifications.
The reference's observed module count and installed kWp remain null. Confidence
is low, scenario spread is sensitivity rather than a statistical interval, and
post-installation LiDAR limits retrospective independence.

`datasets/inputs/roof_capacity/pvgis/` records `generation_role` as
`counterfactual_validation_only`, `incremental_proposed`, or `existing_unverified`.
Weather period and losses are unset. Select one scenario; never sum alternatives
or treat retrospective generation as actual existing PV. Zero capacity skips
simulation. These provisional records have `energy_sharing_eligible: false` and
the case-study PVGIS importer rejects them until a separately verified generation
record is supplied. Existing hourly-import settings without these new fields
retain their prior behavior.

See [the complete rooftop report](../reports/roof_capacity/A160/README.md).

All paths below are relative to the repository root. A160 and the mixed-use
participants are identified in the V2.2 handover; their geometry/parameters remain
unverified. Empty `_TEMPLATE` files are not observations. Candidate identities
are in `datasets/inputs/case_study_candidates.csv`, separate from a validated
`building_cluster.csv` inventory.

## Building inventory and model inputs

Fill `datasets/inputs/building_cluster.csv` from its template after choosing the
case study. One record per building; exactly one designated host. Floor area is
positive m², coordinates are WGS84 decimal degrees and timezone is an IANA name.
Record the source and confidence of each building's attributes.

`predict-bdg2 --input FILE` expects one row per building and hourly interval:

| Column | Meaning |
| --- | --- |
| timestamp_utc | ISO-8601 with `Z` or explicit UTC offset; no naive timestamps |
| building_id | Stable participant identifier, used only to label outputs |
| building_use | Supported model use, currently Office / Education / Retail |
| floor_area_m2 | Area corresponding to the demand estimate; positive and finite |
| latitude | Location in decimal degrees; also a climate/context feature |
| timezone | E.g. Europe/Madrid |
| air_temperature_c | Corresponding hour's temperature in °C; missing values use training-only imputation |

The measured-data model is a conditional estimator, not a real-time forecasting
service. Actual/predicted weather must be sourced explicitly. Unknown residential
uses are rejected; a residence hall is not a household archetype.

Outputs use `predicted_electricity_kwh`, model version, scenario ID and a provenance
label. Historical meter labels and IDs never become prediction features.

## Office surrogate inputs

The generic `predict` command follows `demand_model.route` and `artifact` in
`config/project.json`; the current route is the office EnergyPlus surrogate.
`predict-office` selects that route explicitly. Its input template is
`datasets/inputs/office_surrogate_features_TEMPLATE.csv`.

The surrogate requires `timestamp_utc`, building ID, `archetype`, exact reference
floor area, Europe/Madrid timezone, temperature, a six-hour past/current rolling
temperature mean, hourly global solar radiation in W/m² and the four operation
parameters in `config/simulation.json`. It rejects different geometry/area and
parameter values outside the discrete simulated levels. These inputs describe a
reference simulation scenario, not measured occupancy at an actual building.

Tested geometry is 511.1574 m² for the official reference office. A different host
requires a physics-model/domain update before inference; there is no silent
area-based extrapolation. This restriction deliberately keeps simulation accuracy
claims separate from actual-building applicability.

## Time conventions

- BDG2 source meter timestamps are local wall time. Its weather documentation
  explicitly ignores DST. Training retains that regular source time basis and
  does not fabricate unambiguous UTC meter timestamps.
- The case-study pipeline requires explicit UTC instants. For the measured-data
  model, calendar features use local winter-standard time to match the training
  convention. Manual schedule adjustments use local civil time including DST.
- Hourly PV, demand and coefficients must have identical, continuous UTC indices.
  Missing hours, duplicates and mismatched years fail rather than silently filling.
- No automatic historical-year or typical-year relabeling is implemented. That
  calendar/day-type decision must be documented once the actual exports exist.

## PVGIS input

`import-pvgis` currently accepts an hourly `time,P,...` CSV. Supply completed
`config/pvgis_settings_TEMPLATE.json` metadata with the export. The importer
converts W or kW average power to one-hour kWh and preserves source minute offsets.
It does not certify rooftop capacity or silently align a `:10` series to `:00`.
Other export schemas require inspection and an explicit adapter.

## Allocation and evaluation

`plan-shares` reads model/simulation forecasts and writes one `beta` per participant
and UTC hour. It refuses observed evaluation meters as plan-generation inputs.
Coefficients must be in [0,1], sum to one and match the evaluation inventory.
The current conventional comparison uses equal fixed shares, an explicit scenario
assumption. It is not claimed as a legally mandated allocation formula.

`match` requires `timestamp_utc, building_id, demand_kwh, data_origin` (or
`predicted_electricity_kwh`) for demand and `timestamp_utc,pv_generation_kwh` for PV.
The host must appear among the demand participants. Grid-only has no installed
PV; the three solar alternatives use identical PV and demand inputs.

Predicted demand can support a planning comparison. Evaluating a forecast-derived
plan against that same forecast does **not** establish AI performance. A meaningful
allocation validation needs held-out observed loads or independent simulation
reference scenarios, with plan inputs kept separate from those evaluation targets.

## Costs, emissions and benefit proxies

Complete `config/impact_assumptions.json` before running `impacts`. Every numeric
assumption needs a `sources` entry containing `assumption_name`, `source_url` and
`source_date`. Grid prices are EUR/kWh; carbon factors are kgCO2e/kWh with a declared
accounting year and system boundary. No assumed current price or carbon factor is
embedded in the code.

Money/emissions outputs are scenario screening proxies. Export compensation is a
flat per-kWh assumption with no billing cap; it is not statutory bill settlement.
No exported-energy carbon credit is assumed. Simple payback is produced only for
a complete calendar year and positive net annual savings after O&M; no discounting,
taxes or financing. Participant savings are gross before capital/O&M cost sharing.
No claims about household vulnerability or real community formation are inferred.
