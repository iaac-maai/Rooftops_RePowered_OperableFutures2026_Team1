# Demand-model benchmark

Validation-selected model: **demand_baseline_hour_of_week**. XGBoost improves the best validation baseline: **False**.

MAE and RMSE are hourly kWh; NMAE is MAE divided by mean measured load.

model,split,rows,buildings,mae_kwh,rmse_kwh,nmae_mean_load,mae_wh_per_m2
demand_baseline_hour_of_week,validation,1051949,62,108.94782295398922,296.1979436384538,0.6739196463629331,11.585285381085964
demand_baseline_seasonal,validation,1051949,62,111.17561094056715,297.5966053540249,0.6877000969619345,11.844890379825085
demand_xgboost,validation,1051949,62,123.56135476490276,325.27179564330396,0.7643147173528644,10.881659360027582
demand_baseline_hour_of_week,test,1009700,60,101.97494256836127,169.15920181909823,0.6688395061563305,13.420951095144565
demand_baseline_seasonal,test,1009700,60,103.98426057548986,172.79652247477594,0.6820183443076536,13.631472305489437
demand_xgboost,test,1009700,60,146.54575737189384,300.3597215303027,0.9611732992564901,14.80850775105944

## Limits

- This is a reproducible initial experiment, not a tuned or locally validated final model.
- Entire buildings are held out; sites can appear in multiple splits.
- Reference timestamps remain in their source time basis; these are not Barcelona demand series.
- Small retail cohort and uneven building/site coverage limit confidence.
- Manual schedules are not learned occupancy responses. No household residential demand model is trained.
- Missing meter targets are excluded, not imputed. Temperature imputation and encoding fit training rows only.
- The same sampled training rows fit all three models. Validation/test use all retained holdout hours.
- If XGBoost fails to beat the baseline, prefer the baseline for current estimates and revisit the modeling route.
