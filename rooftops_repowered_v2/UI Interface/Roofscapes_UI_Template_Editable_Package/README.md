# Roofscapes (Re)Powered V2 — User Interface Template

**Status:** editable, standalone front-end demonstration. Not connected to live backend calculations.
**Site:** A160 (Carrer dels Almogàvers 160), Barcelona — with ITAEB, municipal housing at Ciutat de Granada 95–97, and NH Barcelona Diagonal Poblenou as hypothetical participants.
**Primary repo:** https://github.com/SindhujaDavuluri/rooftops_repowered_v2

## Run and edit

Open `index.html` in a modern browser. The design is a single self-contained HTML file: HTML, CSS, JavaScript, illustrations, and graphical data are embedded. No account, server, internet access or build step is required for the interface itself. External evidence links need internet access.

The interface uses a warm architectural-paper visual language, dark green navigation, muted PV blue, and yellow connecting lines. The urban illustration deliberately uses Barcelona-style chamfered blocks but is explicitly **conceptual**, not accurate parcel geometry or a field-surveyed map. To connect a genuine spatial map later, use a cadastral basemap and georeferenced footprints rather than treating the illustration as coordinates.

## Functional screens

| Screen | User experience | Backend integration target |
|---|---|---|
| Overview | A160 and three participant typologies; roof status; conceptual demand rhythm chart | `datasets/inputs/case_study_candidates.csv`, project config and report readiness |
| Roof intelligence | Choose conservative, base or optimistic; see two separate capacity metrics | `datasets/processed/roof_capacity/A160/{retrospective,additional}/roof_capacity_scenarios.csv` and mapped GeoJSON |
| Solar production | Evidence gate for unknown existing installed kWp and unrun PVGIS series | `pipeline/step_03_pvgis/importer.py`; normalized hourly PV file once available |
| Demand prediction | Educational schedule profiles; office surrogate evaluation status | `pipeline/step_05_simulation_surrogate/`, held-out test metrics; later mixed-use simulation results |
| Energy sharing | Grid-only, host-only, fixed, demand-informed; no fictitious scenario savings | `pipeline/step_07_energy_balance/evaluate.py` and share planner |
| Impact assessment | Environmental, economic, social output placeholders | `pipeline/step_08_impact_metrics/screen.py` with dated transparent assumptions |
| Sources & evidence | Public project source links and provenance taxonomy | Link to each dataset's recorded provenance and model card |

The scenario buttons, 24-hour slider, typology selector, sharing rule selector and JSON export are interactive. The time profiles are *illustrative normalized patterns*, not measured or EnergyPlus-generated kWh values. The `roof` scenario values are reported from the connected repository as of 15 November 2026, but remain low-confidence screening estimates. Buttons do not execute Python modules or contact PVGIS.

## Verified vs pending separation

- **Existing A160 PV:** visually established in orthophotography; **installed kWp, panel Wp, and inverter output still unknown**. Never use 110.88 kWp (retrospective hypothetical potential) as its observed capacity.
- **Retrospective A160 capacity:** conservative 95.34 kWp, base 110.88, optimistic 116.76, assuming V1-style 420 Wp hypothetical modules. A post-installation LiDAR capture limits independent validation.
- **Additional A160 capacity:** conservative 0 kWp, base/optimistic 1.26 kWp, conditional, not engineering approval.
- **Observed panel reference coverage:** 410.72 m² image interpreted, not observed kWp. Base spatial IoU 0.265.
- **Office demand model:** XGBoost test MAE 0.648 kWh per simulated hour; one 511.16 m² reference geometry and 36 operation configurations. This does not verify real A160 accuracy or the other building typologies.
- **Hourly PV / demand / sharing / impact:** pending case-study integration; no fake annual generation, avoided emissions, payback or tariff savings displayed.

## Practical Codex development sequence

1. Refactor HTML into components but **preserve the visual layout and evidence labels**; no necessity to rewrite in React until backend integration warrants it.
2. Replace hard-coded case-study information with a validated building inventory; retain geographical source and confidence fields.
3. Load the scenario CSVs/GeoJSON via a read-only API and render actual A160 roof polygons, observed PV footprints, and predicted panel layouts. Keep retrospective and *additional* roof analyses distinct.
4. If actual installed PV system specs are established, introduce a separately sourced `existing_pv_kwp` record; maintain null if not verified.
5. Integrate PVGIS hourly data through a validated file/backend endpoint; normalize UTC timestamps and document local daylight-saving presentation.
6. Feed the office-surrogate's supported in-domain predictions and independently simulated mixed-use reference demand into an aligned hourly chart. Reject out-of-domain model inputs instead of silently rescaling floor area.
7. Connect scenario selection to actual energy-balance outputs. Require energy conservation, consistent generation and demand across comparison strategies, and independent evaluation of demand-informed coefficients.
8. Only activate environmental, economic and social KPIs after dated emissions/tariffs/investment assumptions are supplied. Show ranges or caveats as appropriate.
9. Maintain a public provenance drawer per chart or metric, with source URL, capture date, model version, and data-origin category (`observed`, `modeled`, `assumed`).
10. Test keyboard navigation, mobile layout, empty-state handling, long labels, export/serialization and browser differences. Avoid interpreting this as grid-control software.

## Export format

The download button exports a JSON UI scenario **template** with the selected rooftop capacity scenario, active typology explorer and sharing strategy. Empty generation, demand and results fields remain `null`, and the JSON explicitly says it is not a simulation result. It is not yet a valid execution config for the Python pipeline without backend validation.

## Original sources

- [V2 README and reports](https://github.com/SindhujaDavuluri/rooftops_repowered_v2)
- [A160 rooftop report](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/README.md)
- [V1 roof-intelligence repository](https://github.com/iaac-maai/Rooftops_RePowered_OperableFutures2026_Team1)
- [PVGIS](https://photovoltaic-geographic-information-system.ec.europa.eu/)
- [EnergyPlus](https://energyplus.net/)
- [A160 architectural project](https://www.batlleiroig.com/en/projects/oficines-almogavers-160-a-barcelona/)
