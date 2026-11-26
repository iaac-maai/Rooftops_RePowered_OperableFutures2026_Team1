# Research method and current limitations

## Measured-data reference experiment

BDG2 supplies publisher-cleaned hourly electricity labels, joined to metadata by
building ID and weather by site plus source timestamp. Sources and raw checksums
are retained. The audit scans all eight CSVs, including the full 1.34-million-row
Catalonia certificate export. Certificates and city/regional totals are contextual
references, not building-level hourly targets.

Buildings require valid floor area/location, at least 80% retained electricity
coverage, nonnegative readings and a declared building use. Cleaning is not
retrofitted to improve model metrics. Missing targets are excluded, not filled.
Weather features can be missing; imputation fits only the training partition.
Coverage-based cohort selection spans source periods and is disclosed separately
from model fitting. All model families use the same sampled training rows.

The first experiment used 70 buildings and a 300,000-row training sample. It failed
the primary validation MAE gate; its results and model artifacts are archived in
`reports/demand_model/experiments/initial70/` and
`pipeline/models/experiments/initial70/`.

The expanded, predeclared experiment used up to 150 buildings per use, latitude
as an inference-available context feature, a 600,000-row training sample, and an
area-weighted absolute-error objective. Targets are Wh/m² internally; predictions
and primary metrics are kWh per hourly interval. Area-weighted intensity loss
aligns the training objective with absolute whole-building kWh error.

Entire buildings are disjoint across training, validation and test. The expanded
test pool excludes all 70 buildings from the initial experiment. Retail was fully
represented in the initial cohort, so the expanded experiment has **no untouched
retail test buildings**; retail is present in training/validation only. Tests cover
unseen office and education buildings. Sites are shared between partitions and
latitude can act as a site proxy: this is not unseen-site or Barcelona validation.
Both source years are evaluated; this is conditional unseen-building estimation,
not a chronological future-weather forecast evaluation.

The expanded XGBoost also failed to beat the hour-of-week baseline on primary MAE.
The model registry therefore recommends that baseline; XGBoost is retained as an
experimental artifact. Small gains on an alternative normalized metric do not
override failure on the predeclared kWh metric. No extra tuning is done against
the reported test outcomes. See the generated model card and per-building/type
metrics for the evidence.

## Agreed next route: office physics-simulation surrogate

The user chose to explore this route after the two measured-data experiments.
Start with office archetypes and explicit operating schedules. Use an established
simulator, then train the same primary AI family on its outputs. Hold out whole
simulation configurations, not random hours from the same configuration.

This route estimates simulator response. It does not independently validate real
Barcelona meter behavior. Reference geometry, construction, HVAC, schedules and
weather must all be recorded. A U.S. office example with Barcelona weather remains
a hypothetical archetype unless local parameters are supported. Thermal loads in
an ideal-loads model cannot simply be relabeled electricity; use actual electric
meters/end uses or document the conversion assumptions.

## Independent accounting

Energy accounting is deterministic and separate from AI. PV comes from PVGIS
exports for the eventual selected roof. The balance tests require nonnegative
energy, conservation, aligned hours and complete inventories. A case where the
host already consumes all PV cannot show additional total import/emissions gains
just because shares change. Some collective allocations can perform worse.

## Publisher and method references

- [BDG2 meter units, source time and cleaning](https://github.com/buds-lab/building-data-genome-project-2/wiki/Meters-data-features)
- [BDG2 weather features and DST convention](https://github.com/buds-lab/building-data-genome-project-2/wiki/Weather-features)
- [BDG2 publication](https://doi.org/10.1038/s41597-020-00712-x)
- [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html)
- [Grouped model evaluation](https://scikit-learn.org/stable/modules/cross_validation.html)
- [EnergyPlus official releases](https://github.com/NatLabRockies/EnergyPlus/releases)
- [CEA source and dependencies](https://github.com/architecture-building-systems/CityEnergyAnalyst)
