# Seasonal demand baseline

Estimate electricity demand using seasonal training-set averages, with building
type and floor-area normalization where appropriate. Evaluate on the same
held-out buildings as XGBoost; do not use validation targets to fit averages.

Status: implemented and benchmarked. The hour-of-week baseline performed better
on the current validation cohort; retain this seasonal baseline for comparison.

Save any fitted baseline artifact to
`pipeline/models/demand_baseline_seasonal.joblib` (relative to the project root).
