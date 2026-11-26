# A160 rooftop inputs

The real case is cadastral building **2635601DF3823F**, Almogàvers 160 within official street range 154–164.

- `A160_footprint.geojson`: official cadastral geometry, WGS84.
- `A160_observed_panel_coverage.geojson`: independent image-interpreted reference for retrospective scoring; not an installed-capacity measurement.
- `A160_observed_array_envelopes.geojson`: occupied PV row blocks, including spacing; used only in additional feasibility.
- `A160_current_access_exclusions.geojson`, `A160_current_high_roof_boundary.geojson`: current image interpretation for additional feasibility only; not survey/as-built clearance approval.
- `A160_observed_annotation.json`: annotation rules, native/resampled resolution, sensitivity, hashes and unknown installed specifications.
- `pvgis/`: separate counterfactual, incremental and unknown existing-installation records. Never sum scenarios or treat retrospective generation as existing generation.

`config/a160_assessments.json` controls the actual dual assessment; `config/a160_pv_reference_annotation.json` records manual digitization. Generic `lidar_tiles_TEMPLATE.csv` and `config/roof_capacity.json` remain for the stricter future reviewed/pre-installation workflow; they are not A160's active input route.

See [the milestone report](../../../reports/roof_capacity/A160/README.md) for dates, assumptions, limitations and reproducible commands. All geometry exports are WGS84; calculations use EPSG:25831.
