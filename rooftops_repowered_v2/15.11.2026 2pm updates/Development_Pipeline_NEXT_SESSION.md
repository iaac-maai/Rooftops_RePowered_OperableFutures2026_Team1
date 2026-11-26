# Roofscapes (Re)Powered V2 — Future execution pipeline

**Snapshot:** 15 November 2026. **PLANNED ONLY. Do not run this pipeline during the pause.** Repo: https://github.com/SindhujaDavuluri/rooftops_repowered_v2 ; remote `main` reviewed at merge commit `de3ea0ca5f2c022af5f4d50d054a0c897e5eb914`.

## Why the order matters

```text
EXISTING V2: A160 roof screening + official hypothetical PVGIS + read-only UI + initial office surrogate
            |                         |
            v                         v
   [1] SOURCE / DATA REVIEW        (Keep existing models and the UI unchanged)
            |
   [2] DOWNLOAD + VERIFY CITY 3D + RHINO 8/HONEYBEE
            |
   [3] BUILD A160 GEOMETRY, THERMAL ZONES + PROVENANCE
            |
   [4] RUN VALID ENERGYPLUS A160 SCENARIOS + QA --------> GATE A
            |
   [5] TRAIN SEPARATE A160 XGBOOST SURROGATE + BASELINES -> GATE B
            |
   [6] PRODUCE EDUCATION / RESIDENTIAL / HOTEL PHYSICS ARCHETYPES
            |
   [7] ALIGN PV, WEATHER, TIMESTAMPS AND PARTICIPANT ASSUMPTIONS -> GATE C
            |
   [8] EVALUATE HOST-ONLY, FIXED, DEMAND-INFORMED SHARES + TEST CONSERVATION
            |
   [9] SOURCE IMPACT FACTORS, COMPARE ENVIRONMENT, COSTS, PARTICIPATION
            |
  [10] INTEGRATE *VALIDATED AND EXPLICITLY SIMULATED* RESULTS IN EXISTING UI
            |
   RESEARCH REPORT / REPRODUCIBLE DEMO
```

## Execution stages, contracts and acceptance gates

| Stage | Inputs | Tools / model | Outputs | Hard exit condition |
|---|---|---|---|---|
| 0. Baseline and package review | This package, current GitHub main, existing cached source/model artifacts | Read-only audit, source hashes | Baseline inventory + decision register | No model overwrites or silent changes |
| 1. Prepare synthetic evidence | `published_site_facts.csv`; `geometry_hypotheses.csv`; `energyplus_scenario_parameters.csv`; 2017 schedule/proxy CSVs; source register | Pandas, documented assumptions | Validated low/base/high inputs for four buildings | Hourly kWh proxy marked **LITERATURE_CALIBRATED_SYNTHETIC**, not metered/ML labels |
| 2. Rhino 8 georeferenced geometry | Barcelona 2026 3D DWG for el Parc i la Llacuna; A160 Catastro 2635601DF3823F, ICGC LiDAR / ortho, plans | Rhino 8, DWG importer, Rhino layer protocol, Honeybee | `A160_geometry_review.3dm` + geometry/source manifest + thermal-zone inventory | Confirm building ID, units, CRS and validity; stop if unverified |
| 3. A160 EnergyPlus model | Reviewed Honeybee zones, envelope/window and electric HVAC assumptions, weather EPW, scenario schedules | Grasshopper, Honeybee, OpenStudio/EnergyPlus; optional direct IDF fallback | HBJSON/OSM/IDF, `.err`, hourly facility-electricity CSV, simulation manifest | 8760 complete hourly electric kWh, fatal errors = 0, end-use and literature plausibility audited |
| 4. A160 AI model training | **EnergyPlus outputs only** from stage 3, grouped case/config IDs, explicit weather/schedule features | XGBoost vs hour-of-week and schedule-aware linear baselines; config-held-out evaluation | *New* versioned model, feature schema, split manifest, metrics and model card | Must beat relevant baselines on held-out configs; if not, retain baseline, report failure |
| 5. Other uses | ITAEB / 18 homes / NH architectural evidence + independent archetype assumptions | Independent EnergyPlus typology simulations; validated surrogate only when warranted | Education, residential and hospitality hourly simulated profiles | No scaling 511 m² office model into other uses or claiming measured accuracy |
| 6. Common weather/calendar experiment | PVGIS SARAH3 **2017** scenario, EnergyPlus EPW, timestamps and DST conventions | Explicit weather/calendar normalization + scenario manifest | Compatible year/time/reference comparison or a documented no-comparison gate | Cannot join unrelated IWEC typical-year to PVGIS 2017 just because year tags agree |
| 7. Energy balance | Explicitly admissible PV generation and demand, approved candidate participants, beta schedule | Existing `pipeline/step_07_energy_balance/evaluate.py` | Host-only, grid-only, fixed and demand-informed simulated comparisons | Real-case study `match` must reject hypothetical PV; separate research-only test harness if needed; conservation checks |
| 8. Impact | Hourly results, dated tariffs, O&M/capex and emissions data | Existing impact code + sensitivity analyses | Marginal grid-import impact, economics, benefit distribution | No unreferenced rates, no false avoided emissions if host uses all PV |
| 9. UI integration | Real reports + explicit model/domain/status flags | Existing `ui/` Python read-only server, allowlisted APIs | New labeled site-demand and study/impact views | Pending vs simulated vs observed always explicit; no credentials served |
| 10. Review and publication | Model cards, traceable sources, plots/notes, reproducibility instructions | Presentation/research reporting | Validated methodology + project deliverables | Claims limited to evidence and actual validations performed |

### Staged execution is **not** authorization today

Only **after a new, explicit user instruction** should Codex do any code, downloading, tests, model execution, training, commits or UI changes. Stages 2–4 first; do not jump straight to model training. Stage 5 can be parallelized after A160 physics QA if justified, but labels and evaluation must remain typology-specific. Do not merge actual and hypothetical PV roles.

### Do not overwrite

- `pipeline/models/` trained artifacts; clone/version A160 model and retain original baseline and manifests.
- `reports/roof_capacity/A160/` frozen retrospective geometry, reference segmentation, dates and IoU.
- `config/a160_existing_pv.json`: actual installed module count/Wp/kWp, tilt/azimuth and inverter information remain unknown.
- `config/pvgis_hypothetical.json` and PVGIS `hypothetical/` data remain **sharing-ineligible**.
- Existing seven-view visual language, source drawer, evidence states and null/pending UI behavior.

### Decision records to preserve

1. **V1 → V2:** previously Barcelona-wide potential/roof segmentation, now one office solar host and three different uses. Reason: defendable AI + allocation experiment, realistic scope, faculty emphasis on weather.
2. **A160 over 165:** office host with public building documents and visible installed PV; 165 documented 20 kWp is a different building, optional comparator, not A160 capacity.
3. **Two roof studies:** retrospective hypothetical potential vs additional physical potential after existing arrays; never add alternatives.
4. **Failed BDG2 improvement:** keep empirical XGBoost failure visible; AI value must beat strong baselines.
5. **Physics surrogate:** 36 configurations of a 511.1574 m² US reference small office, Barcelona IWEC; reported test MAE ~0.648 kWh/h only against simulator output, not real A160.
6. **PVGIS official acquisition:** 2017 SARAH3, hypothetical 95.34/110.88/116.76 and 1.26 kWp, 14% loss; actual installed kWp stays null; manual downloads not required for obtained sensitivity cases.
7. **Synthetic assumptions:** one published-facts layer + analyst-created schedules and low/base/high EnergyPlus parameters + literature-calibrated hourly **proxies**, no real hourly meters.
8. **Rhino route:** Barcelona 2026 3D DWG is a geometric starting point, not a thermal model, and plugin compatibility on user's workstation remains untested.
9. **UI:** locally running, read-only seven-view app; expand when validated outputs exist; no unnecessary redesign or 3D claims without a geometry asset.
10. **Fair comparison:** if A160 absorbs all PV, changing recipients cannot claim new avoided imports/emissions; forecast-guided shares need independent demand reference.
11. **Pause mode:** Codex only reads handover and reports understanding in the next session; nothing executes now.

## Scientific evidence

- Repo baseline and limitations: https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/NEXT_STEPS.md
- Geometry evidence: https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/README.md
- Current UI and PVGIS: https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/ui/docs/pv-integration/README.md
- Input contracts: https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/docs/DATA_CONTRACTS.md
- Barcelona 3D: https://portaldades.ajuntament.barcelona.cat/mapes/146
- Rhino 8 DWG: https://docs.mcneel.com/rhino/8/help/en-us/fileio/autocad_dwg_dxf_import_export.htm
- Ladybug Tools: https://github.com/ladybug-tools/lbt-grasshopper/releases
- Honeybee model to OSM: https://docs.ladybug.tools/hb-energy-primer/components/5_simulate/model_to_osm
- Full literature references: `Research_Source_Register_UPDATED.md` and synthetic ZIP `datasets/synthetic/a160_cluster/source_register.csv`.
