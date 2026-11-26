# Saved models

Store all trained models and fitted baselines here, along with feature schemas
and training manifests. Paths are relative to the project root:

- `pipeline/models/demand_xgboost.joblib`
- `pipeline/models/demand_baseline_hour_of_week.joblib`
- `pipeline/models/demand_baseline_seasonal.joblib`
- `pipeline/models/demand_office_energyplus_surrogate.joblib`: alternative office
  demand surrogate trained on physical simulations when available.
- `pipeline/models/office_simulation_baselines.joblib`: simulation benchmark estimators.

Feature schemas and training manifests sit beside the artifacts. Initial measured
experiments are retained in `experiments/initial70/`. Current generated model cards
in `reports/` determine which models passed their baseline gates; the existence of
a model file does not establish local accuracy. All training implementations write
here rather than create a model directory within `datasets/`.
