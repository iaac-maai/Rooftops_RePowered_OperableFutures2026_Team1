# Dataset audit

- bcn_electricity_2025: audited; 209,105 rows.
- bcn_municipal_pv_2025: audited; 211 rows.
- catalonia_energy_certificates: audited; 1,342,960 rows.
- catalonia_self_consumption_registry: audited; 138,769 rows.
- catalonia_hourly_electricity_demand: audited; 7,943 rows.
- bdg2_metadata: audited; 1,636 rows.
- bdg2_cleaned_electricity: audited; 17,544 rows.
- bdg2_weather: audited; 331,166 rows.

## Interpretation

- BDG2 cleaned electricity is hourly kWh in site-local wall time. Missing readings remain missing, never zero-filled.
- Cleaned BDG2 labels are publisher-filtered observations; their coverage is not raw meter completeness.
- Aggregate Catalonia/Barcelona data and certificates are not building-level hourly training targets.
- Catalonia demand uses one date row with H01–H25 columns; inspect DST conventions before reshaping.
- BDG2 has no observed hourly occupancy schedules. Manual scenario schedules remain external assumptions.
- See column_quality.csv for field names, missingness and electricity meter ranges.

## Issues


- The downloaded Barcelona 2025 electricity source ends November 30: it is not a complete annual total.
