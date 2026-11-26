# Demand-model benchmark

Validation-selected model: **demand_baseline_hour_of_week**. XGBoost improves the best validation baseline: **False**.

MAE and RMSE are hourly kWh; NMAE is MAE divided by mean measured load.

model,split,rows,buildings,mae_kwh,rmse_kwh,nmae_mean_load,mae_wh_per_m2
demand_baseline_hour_of_week,validation,238085,14,53.76883827280107,76.08560437093969,1.4497122939308038,19.81137859449209
demand_baseline_seasonal,validation,238085,14,54.85392711836023,79.03821346119221,1.4789683963489593,19.996289844596138
demand_xgboost,validation,238085,14,59.18053246629594,103.0987879616266,1.5956220783955364,18.827431367174007
demand_baseline_hour_of_week,test,233241,14,142.1927692444129,216.73286033020617,0.7666220033402853,16.738685188712406
demand_baseline_seasonal,test,233241,14,144.37833210158476,219.40578978473246,0.7784053069843069,17.459010504505507
demand_xgboost,test,233241,14,185.5122645805207,302.74208947834927,1.0001759208476766,34.470502676270556

## Limits

- This is a reproducible initial experiment, not a tuned or locally validated final model.
- Entire buildings are held out; sites can appear in multiple splits.
- Reference timestamps remain in their source time basis; these are not Barcelona demand series.
- Small retail cohort and uneven building/site coverage limit confidence.
- Manual schedules are not learned occupancy responses. No household residential demand model is trained.
- Missing meter targets are excluded, not imputed. Temperature imputation and encoding fit training rows only.
- The same sampled training rows fit all three models. Validation/test use all retained holdout hours.
- If XGBoost fails to beat the baseline, prefer the baseline for current estimates and revisit the modeling route.
