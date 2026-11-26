# Hour-of-week demand baseline

Estimate electricity demand using training-set averages grouped by building type
and hour of week. Use consistent floor-area normalization where appropriate and
evaluate on the same held-out buildings as XGBoost.

Status: implemented and benchmarked; currently the recommended measured-data
estimator by validation MAE. This is a reference baseline, not local accuracy
validation for Barcelona.

Save any fitted baseline artifact to
`pipeline/models/demand_baseline_hour_of_week.joblib` (relative to the project root).
