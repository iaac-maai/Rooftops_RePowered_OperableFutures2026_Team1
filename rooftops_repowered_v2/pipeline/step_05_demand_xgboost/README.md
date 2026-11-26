# XGBoost electricity-demand model

Primary model for hourly building electricity demand, trained on audited BDG2
meter data, building metadata, weather and calendar features. Compare against
the two reference baselines on held-out buildings. Manual operating schedules
must be identified as external scenario adjustments unless supported by training data.

Status: implemented and benchmarked. Both measured-data experiments failed the
primary validation MAE gate. Retain them as evidence and use the hour-of-week
baseline for the current measured-data route. The alternative office physics
surrogate is implemented separately in `pipeline/step_05_simulation_surrogate/`.

Save the trained model to `pipeline/models/demand_xgboost.joblib`, with its feature
schema and training manifest alongside it (paths relative to the project root).
