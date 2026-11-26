# Roofscapes (Re)Powered V2 — Implementation Pipeline

**Current implementation:** See [README.md](README.md),
[progress and next steps](reports/NEXT_STEPS.md) and
[the method](docs/METHOD.md). The measured-data benchmark was evaluated and did
not establish an XGBoost gain. The user then selected the office EnergyPlus
simulation-surrogate route. The V2.2 handover identifies A160 and a mixed-use
cluster; roof geometry and site assumptions remain unverified. V1 roof-capacity
code is integrated in `pipeline/step_02_roof_capacity/`. All trained artifacts
belong in `pipeline/models/`. The original staged plan follows below.

**PV integration update, 15 November 2026:** the UI now compares the existing
image reference against hypothetical roof layouts and reads official hourly
PVGIS capacity-sensitivity results. Acquisition, cache/provenance, temporal
normalization and manual fallback are in [step 03](pipeline/step_03_pvgis/README.md).
Actual installed specifications/generation remain unknown; sensitivity output is
separate and sharing-ineligible. The demand surrogate and frozen roof prediction
remain unchanged.

**2026-11-15 rooftop milestone update:** A160 footprint and dated public sources
are obtained. Existing PV is confirmed. Run `python -m pipeline roof-feasibility`
for separate retrospective validation and conditional additional-PV outputs.
See [the results](reports/roof_capacity/A160/README.md); this update supersedes
the older roof-selection/potential assumptions below. Post-installation LiDAR
limits retrospective independence, installed kWp remains unknown, and the demand
surrogate is unchanged. Downstream pipeline development remains deferred.

**Studio constraint:** Post-midterm; approximately four-to-five weeks remain as of November 14, 2026. **One** final Barcelona building cluster, **one** primary trained AI model, transparent impact evaluation. The tool is a **pre-installation design support prototype**, not a live energy-community controller.

## Central research question

How can AI-assisted electricity-demand estimation guide the use and distribution of limited rooftop solar production among a small group of Barcelona buildings, subject to preliminary environmental, economic and social constraints?

## Stage 0 — Define test and data definitions (day 1)
- **Inputs:** Study objective, required metrics, permitted time frame, geographic scale.
- **Work:** Freeze one host + three to five consumer buildings; choose all timestamps in one convention (Europe/Madrid local with UTC normalization and DST handling); distinguish electricity from thermal demand; specify data provenance.
- **Tools/precedents:** Barcelona Energy Resources Map; Spanish collective self-consumption framework.
- **Outputs:** `inputs/building_cluster.csv`, `inputs/host_roof.csv`; model target defined as hourly **electricity kWh**.
- **Gate:** Selected host can plausibly accommodate PV; participant eligibility and participation are described as hypothetical if unverified.

## Stage 1 — Download and audit datasets (days 1–3)
- **Inputs:** Public catalogs, Building Data Genome 2 (BDG2), Barcelona electricity, Catalonia certificates/PV registry, Catalonia hourly demand.
- **Work:** Run `download_datasets.py`; audit schema, completeness, site types, units, timezones, licensing and access failures. Select relevant office/retail/institutional BDG2 electricity meters. Do **not** use Catalonia hourly system demand as building-level labels.
- **Tools/precedents:** BDG2 (Miller et al., Scientific Data 2020); pandas; Barcelona Open Data; ICAEN certificates.
- **Outputs:** `raw/*`, `processed/data_quality_report.csv`, `processed/train_buildings.csv`, `processed/train_meter_hourly.csv`.
- **Gate:** Have real electricity targets and building metadata with consistent IDs; document unavailable variables.

## Stage 2 — Select and describe the Barcelona cluster (days 3–5)
- **Inputs:** Barcelona Solar Map, actual host characteristics, Cadastre or existing building inventory, energy certificates, published opening hours.
- **Work:** Choose one PV host roof and 3–5 consumers; record area/type, source, operating hours and assumptions. Use available PV area/capacity instead of repeating rooftop vision/segmentation training.
- **Tools/precedents:** Barcelona municipal solar atlas; Cadastre INSPIRE; Barcelona municipal shared-self-consumption service.
- **Outputs:** `inputs/building_cluster.csv`, `inputs/host_roof.csv`, `inputs/source_register.csv`.
- **Gate:** A plausible cluster with known coordinates, use types and estimated PV capacity.

## Stage 3 — Generate PV output from established tool (days 5–7)
- **Inputs:** Host location, installed kWp, panel tilt/azimuth/losses, selected PVGIS weather or time series.
- **Work:** Export hourly PV output with the **PVGIS web UI**, record configuration and time basis. Validate annual yield order of magnitude against the Barcelona Solar Map. No new PV AI training.
- **Tools/precedents:** European Commission JRC PVGIS 6; pvlib **only if** user-configurable PV modeling proves essential.
- **Outputs:** `processed/pv_hourly.csv`, `inputs/pvgis_assumptions.csv`, provenance and uncertainty note.
- **Gate:** Hourly kWh generation properly normalized to selected roof's kWp and timezone. Distinguish actual weather year from typical year.

## Stage 4 — Define controllable building-use scenarios (days 6–9)
- **Inputs:** Selected building uses and area, public opening hours, BDG2 benchmark shapes, optional CEA/DOE archetypes.
- **Work:** Build **manual, editable** office / residential / retail / institutional schedules; weekdays vs weekends; low/base/high activity and weather-sensitive loads. Document synthetic assumptions. Do not invent 'true' meter readings for the case study.
- **Tools/precedents:** City Energy Analyst (CEA); EnergyPlus schedule semantics; DOE End-Use Load Profiles (only for cross-check, not Barcelona ground truth).
- **Outputs:** `synthetic/operation_schedules.csv`, scenario definitions, `processed/demand_scenario_reference.csv`.
- **Gate:** At least 3 coherent scenarios per selected use, with annual consumption plausibility ranges.

## Stage 5 — Train one AI model (days 7–14)
- **Inputs:** BDG2 measured hourly electricity, joined building metadata/weather and calendar features; **or** CEA simulated hourly loads with known operating schedules (alternative, not an additional requirement).
- **Work:** Fit an **XGBoost regressor** for hourly electricity demand in kWh (optionally normalize by floor area). Compare against hour-of-week and seasonal baseline. Hold out entire buildings and evaluate multiple periods. For use without a building's historical meter, only use features available at inference time.
- **Tools/precedents:** BDG2; XGBoost; scikit-learn. **Alternative:** CEA + XGBoost simulation surrogate if scenario controllability is central.
- **Outputs:** `pipeline/models/demand_xgboost.joblib` (relative to project root), `results/model_metrics.csv`, `processed/demand_hourly.csv`, feature/spec documentation alongside the trained model.
- **Gate:** Model improves meaningful baseline **on held-out buildings or simulation configurations**. Report MAE/RMSE and known transfer limitations; if it does not improve baseline, revise target or use baseline honestly.
- **CRITICAL:** BDG2 has no observed building occupancy schedule features; do not imply XGBoost learned schedule response if schedules were not part of training. CEA surrogate is the alternative route when schedule effects must be learned explicitly.

## Stage 6 — Compute rooftop solar-demand matching (days 13–18)
- **Inputs:** `pv_hourly.csv`, `demand_hourly.csv`, proposed sharing coefficients and participant definitions.
- **Work:** Evaluate host-only solar; fixed-share collective allocation; demand-informed **pre-agreed** hourly allocation profiles. Use `min(allocated_pv_kwh, demand_kwh)` for simplified hourly self-consumption; account for imports, exports, settlement assumptions and coefficient constraints. Avoid implying real-time distribution-grid control.
- **Tools/precedents:** Spanish collective self-consumption; pandas/numpy; optional oemof.solph if optimization complexity warrants it.
- **Outputs:** `results/hourly_balance.csv`, `results/scenario_comparison.csv`, `results/sharing_coefficients.csv`.
- **Gate:** Same PV electricity quantity and demand inputs across scenarios; no artificial creation of PV or 'surplus'.

## Stage 7 — Environmental, economic, social screening (days 17–22)
- **Inputs:** Hourly balance, sourced PV capex/O&M and electricity/export tariffs, documented emissions factors, chosen simple participation fairness proxy.
- **Work:** Compute onsite/collective self-consumed PV, grid-import changes, scenario electricity savings, simple payback range, and allocated benefits. Record all assumptions and avoid treating all grid electricity as nonrenewable.
- **Tools/precedents:** REE/REData public statistics, Barcelona municipal shared-PV project; transparent Python accounting.
- **Outputs:** `results/environmental_metrics.csv`, `results/economic_metrics.csv`, `results/participant_benefits.csv`.
- **Gate:** Only claim *additional* avoided emissions or grid imports when the total differs from host-only baseline. Label fair-share proxies as proxies.

## Stage 8 — Explain, verify, present (days 22–30)
- **Inputs:** Dataset quality, held-out prediction results, PVGIS and solar map references, all energy scenario outputs.
- **Work:** Create small visual interface (existing website if it saves time). One host roof, neighbors, hourly production/use curves, three scenario comparison cards, model evaluation, uncertainty, limitations and references.
- **Tools/precedents:** Existing team interface, Plotly/Matplotlib, scikit-learn diagnostics, project-specific AEC 3D visualization.
- **Outputs:** Reproducible proof of concept + research validation section + final studio presentation.
- **Gate:** Clearly distinguish **measured**, **modeled**, and **hypothetical** numbers in charts.

## Keep strictly out of scope

Citywide deployment; a new solar physics model; complete roof obstacle segmentation; real-time dispatch; true commercial energy trading; battery optimization; live grid-data integration; legally binding participant recruitment; full structural/permit validation; social-vulnerability identification; certified carbon life-cycle analysis; local demand-accuracy claims without metered ground truth.

## Source references

- BDG2: https://github.com/buds-lab/building-data-genome-project-2
- BDG2 Scientific Data article: https://doi.org/10.1038/s41597-020-00712-x
- PVGIS: https://photovoltaic-geographic-information-system.ec.europa.eu/
- Barcelona electricity: https://opendata-ajuntament.barcelona.cat/data/dataset/consum-electricitat-bcn
- Barcelona municipal PV: https://opendata-ajuntament.barcelona.cat/data/dataset/plaques-fotovoltaiques
- Catalonia certificates: https://analisi.transparenciacatalunya.cat/d/j6ii-t3w2
- Catalonia self-consumption: https://analisi.transparenciacatalunya.cat/d/2b4s-skfm
- Catalonia hourly demand: https://analisi.transparenciacatalunya.cat/d/hx6q-ykhb
- City Energy Analyst: https://www.cityenergyanalyst.com/
- EnergyPlus: https://energyplus.net/
- oemof: https://oemof.org/
- Barcelona Solar Map: https://www.energia.barcelona/es/generar-energia/generar-energia/mapa-cuanta-energia-puedes-generar
