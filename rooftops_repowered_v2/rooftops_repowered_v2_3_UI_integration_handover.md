# ROOFSCAPES (RE)POWERED V2 — CODEX HANDOVER
## UI integration, next-stage development, and 15 November 2026 conversation + conservation takeaways

**Prepared:** 15 November 2026 (Europe/Madrid)  
**Intended reader:** Codex, working inside the user's V2 repository  
**Main repository:** <https://github.com/SindhujaDavuluri/rooftops_repowered_v2>  
**Observed `main` HEAD at preparation:** `3cb20b9e58152829a87f82d1805ee323e314e79d` (2026-11-15 00:28 UTC, message `test 1`). Check for newer commits **before** editing.  
**Original V1 reference:** <https://github.com/iaac-maai/Rooftops_RePowered_OperableFutures2026_Team1>  
**Assets in the accompanying bundle:** `ui-template/index.html`, `ui-template/README.md`, `ui-template/previews/`, `ROOFSCAPES_UI_ORIGINAL_INTEGRATION_NOTES.md`, `DEVELOPMENT_ROADMAP.png`, and `CODEX_START_HERE.txt`.

> **Execution status:** This is a handover, **not** a report that a Codex job has already started. The user is temporarily away and wants an autonomous, bounded coding pass. Begin the work only when the user supplies this handover to Codex / starts a Codex run. No work is running in the background merely because this document exists.

---

## 0. Primary objective and execution boundaries

**Objective:** Turn the approved, standalone 7-section architectural UI prototype into an **integrated, reproducible, read-only research dashboard** connected to the V2 repository's real outputs, while preparing explicit integration points for A160's existing PV system, hourly demand, allocation comparisons, and impact results. Continue only with subtasks that have sufficient real data; leave everything else visibly pending.

**First-pass deliverable, achievable without external building-meter data:** a locally runnable frontend + minimal, safe data service/JSON adapter reading the current repository, rendering the actual A160 rooftop-scenario CSV and metadata and the office-surrogate reported metrics, showing transparent evidence/pending states, with browser/backend tests and a `README` for local use. Preserve existing interface aesthetics and interactions.

**Non-negotiable:**

1. Work on a **new branch** (e.g., `feat/ui-integration-a160`), not directly on `main`. Do not auto-merge. Make small, auditable commits and supply a diff/PR summary. If branch/repo write access is unavailable, create a local patch/diff and log the blocker.
2. **Do not overwrite or retrain** any trained model under `pipeline/models/` and do not alter V1. Do not regenerate the frozen retrospective roof prediction without an explicit reason and a before/after comparison.
3. **No invented energy numbers.** Never substitute `110.88 kWp` for installed A160 capacity, or the 2015 municipal map's 103.5 kW for current as-built capacity. Existing installed kWp, actual generation and actual metered load are **unknown**.
4. **No fabricated chart values as findings.** The UI may keep illustrative normalized demand curves, but label them `ILLUSTRATIVE_NOT_SIMULATED`, visually separate them from actual datasets, and never render them as hourly kWh.
5. **Do not silently bypass validation gates** in `pipeline/step_03_pvgis/importer.py`, `pipeline/step_05_simulation_surrogate/predict.py`, `pipeline/step_07_energy_balance/evaluate.py`, or `pipeline/step_08_impact_metrics/screen.py`.
6. Use a documented clock convention (`timestamp_utc` and `Europe/Madrid` rendering) and preserve dataset provenance, source acquisition dates, uncertainty, and model versions.
7. Never imply the interface can control the electric grid, trade electricity live, determine legal community membership, or certify rooftop installation / structural / fire compliance.
8. Do not publish private meters, apartment-level usage, residential occupant profiles, or local absolute-path/cache strings through any public API.
9. Keep the user's approved UI layout/branding. A conceptual **chamfered Poblenou block** image is artwork, not surveyed or georeferenced parcels. Any actual map needs real georeferenced footprints.
10. Prefer graceful partially-complete output to a fake 'all green' flow. Stop at missing source inputs and report precisely what is needed.

---

## 1. Current research concept — the explanation to preserve in the UI

**Plain-language question:** A rooftop makes electricity mostly in sunny hours. Offices, schools, homes and hotels need electricity at different times. Can we understand the real roof, predict those demands, and compare whether sharing a **fixed quantity** of rooftop solar among nearby buildings gives better environmental, financial and social outcomes than the host simply using the electricity itself?

**Architecture of the study:**

- **Host:** A160 office, Carrer dels Almogàvers 160, Barcelona (`A160`), architect Batlleiroig. A160 has **existing rooftop PV visible in orthophotography**. Actual installed capacity, module specification and metered generation have not been verified.
- **Core hypothetical participants:** ITAEB at Almogàvers 131 (`ITAEB`, education); 18 municipal rental homes at Ciutat de Granada 95–97 (`CDG95_97`, residential); NH Barcelona Diagonal Poblenou at Àlaba 94–96 (`NH_POBLENOU`, hospitality). Different day types / operating patterns are the selection rationale. Building identity and some architectural/schedule facts are public; actual hourly building meters and participation agreements are not.
- **Optional comparator:** Almogàvers 165 (mixed municipal use with documented 20 kWp solar; this is a **different** building and must never be mixed with A160's capacity).
- **Geographic/legal:** A small nearby cluster is for **hypothetical allocation testing**. Distances, grid connections, eligibility and agreed hourly sharing coefficients must be verified before any legal/commercial claims.
- **Approach:** V1 roof extraction + roof packing → geometry-based potential; PVGIS → hourly photovoltaic generation when real system assumptions are established; EnergyPlus → simulated building electricity; XGBoost → demand prediction **within its trained domain**; deterministic electricity-balance calculations → scenario comparison; sourced metrics → impact screening; UI → transparent explanation.

**Current conceptual status is not full case-study readiness.** UI sections should distinguish `AVAILABLE_REPOSITORY_RESULT`, `PROVISIONAL_ESTIMATE`, `ILLUSTRATIVE`, `MISSING_SOURCE_INPUT`, `VALIDATED_SIMULATION_DOMAIN`, and `UNVERIFIED_REAL_WORLD_TRANSFER` (or equivalent documented enums).

### Why the four typologies were chosen

| Building | Evidence from public sources | Expected contrast | Caveat for modeling |
|---|---|---|---|
| A160 (office host) | Batlleiroig architectural plans; 2022 completion; PV visible in 2025 image | Weekday daytime office demand | The existing surrogate is a **511.1574 m² reference US office**, not actual A160 geometry; current A160 floor-area definitions are not its model's conditioned area. |
| ITAEB (education) | Official school website / course timetables; morning and afternoon shifts | School-day / term-time and later-afternoon patterns | No observed school electricity data; earlier modular school plans may not describe current as-built conditions. |
| Ciutat de Granada 95–97 (18 homes) | Municipal housing report, unit types, build documents | Morning, evening and weekends | Never infer household-level lifestyles; verify whether the planned common-service PV was installed. |
| NH Diagonal Poblenou (hotel) | Hotel's public information, 129 rooms, amenities | 24-hour and weekend/seasonal loads | Real occupancy, HVAC details, conditioned area and meters unavailable. |

Sources: [A160 architecture](https://www.batlleiroig.com/en/projects/oficines-almogavers-160-a-barcelona/), [ITAEB](https://agora.xtec.cat/ins-itaeb/), [municipal 18-home report](https://www.consorcihabitatge.barcelona/es/noticias/el-imhab-entrega-las-llaves-de-18-pisos-de-alquiler-social-en-el-barrio-del-parc-i-la-llacuna-del-poblenou-1405102), [NH hotel](https://www.nh-hotels.com/en/hotel/nh-barcelona-diagonal-poblenou); case-study inventory [`datasets/inputs/case_study_candidates.csv`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/datasets/inputs/case_study_candidates.csv).

---

## 2. Verified repository state at the handover point

As of the observed `main` HEAD:

**A160 rooftop screening is implemented (provisional, low confidence):**

| Quantity | Conservative | Base | Optimistic |
|---|---:|---:|---:|
| Retrospective geometric capacity (assumed new 420 Wp modules) | 95.34 kWp | 110.88 kWp | 116.76 kWp |
| Conditional *additional* capacity today | 0.00 kWp | 1.26 kWp | 1.26 kWp |

- 2025-06-18 finalized ICGC orthophoto; image-interpreted coverage of existing panels 410.72 m², but panel count/Wp/kWp **unknown**.
- 2022-06-01 LiDAR acquired **after PV was already visible**; therefore not clean pre-installation geometry. Retrospective base IoU ≈ **0.265**, so no strong layout-accuracy claim.
- 2026-03-16 provisional imagery is a visual check only; registration and native resolution for label transfer are not verified.
- Barcelona municipal map returned 103.5 kW / 1,094.8 m² / 129,323 kWh/yr from a **2015-dated legacy polygon associated geometrically with the site**; not a modern A160 measurement or verified roof record.
- Current upper-roof additional panels are only 0 to 3 hypothetical 420 Wp modules, with no as-built access or safety approval.
- The repo reports 49 passing tests, 0 failures from its **committed verification report**, not independently rerun by this handover writer. Running tests anew is task A0.

**Demand modeling:**

- Initial real-meter BDG2 XGBoost experiments did **not** beat the hour-of-week baseline on the predeclared kWh metric; document both negative experiments.
- Selected physics-to-ML route simulates 36 office operation configurations in EnergyPlus with Barcelona IWEC weather (~315,360 labeled hourly outputs), trains XGBoost and evaluates disjoint operation configurations. **Test MAE: XGBoost 0.6481 kWh/h; schedule-aware linear 1.4648; hour-of-week 2.3348.** This is accuracy against *simulated loads*, **not A160 or Barcelona meter accuracy**.
- Model rejects different archetype, floor area, or operation parameters; do not use it directly for residential/school/hotel demand or silently scale it to A160.

**What is NOT done:** verified existing A160 kWp, PVGIS case-study hourly generation, actual A160 demand, non-office archetype demand, proven legal eligibility, evaluated collective impact results, linked live frontend/backend, sourced tariffs and emissions.

**Key source files in V2**:

- [`reports/NEXT_STEPS.md`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/NEXT_STEPS.md)
- [`reports/roof_capacity/A160/README.md`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/README.md)
- [`reports/roof_capacity/A160/readiness.json`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/readiness.json)
- [`datasets/processed/roof_capacity/A160/retrospective/roof_capacity_scenarios.csv`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/datasets/processed/roof_capacity/A160/retrospective/roof_capacity_scenarios.csv)
- [`datasets/processed/roof_capacity/A160/additional/roof_capacity_scenarios.csv`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/datasets/processed/roof_capacity/A160/additional/roof_capacity_scenarios.csv)
- [`reports/roof_capacity/A160/retrospective_validation.csv`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/retrospective_validation.csv)
- [`reports/roof_capacity/A160/reference_separation.json`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/reference_separation.json)
- [`reports/roof_capacity/A160/verification.json`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/verification.json)
- [`reports/simulation_surrogate/model_metrics.csv`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/simulation_surrogate/model_metrics.csv)
- [`config/impact_assumptions.json`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/config/impact_assumptions.json)
- [`docs/DATA_CONTRACTS.md`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/docs/DATA_CONTRACTS.md)
- [`pipeline/step_02_roof_capacity/README.md`](https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/pipeline/step_02_roof_capacity/README.md)

---

## 3. Approved UI asset — integrate rather than redesign

`ui-template/index.html` is the full self-contained browser prototype, with embedded styles, JavaScript and a **conceptual** chamfered-block neighborhood illustration. It is **not** yet backed by Python computations. Companion `ui-template/README.md` describes its current behavior.

Approved presentation style: warm parchment, dark forest-green sidebar, muted blue PV panels, golden dotted sharing connections, architectural 3D/isometric Poblenou blocks, research-evidence labels, generous charts and readable cards. Maintain responsive layouts and accessibility; visuals are conceptual, not a survey map.

Seven existing views in HTML, with JS buttons/data attributes:

1. **Overview**: A160/ITAEB/housing/NH and research status.
2. **Roof intelligence**: conservative/base/optimistic; retrospective vs additional capacity; source evidence.
3. **Solar production**: PVGIS status, currently missing actual installed PV spec.
4. **Demand prediction**: normalized illustrative profiles and office model metrics; no real A160 predictions.
5. **Energy sharing**: selectors for `grid`, `host`, `fixed`, `informed`; currently conceptual, not executed.
6. **Impact assessment**: environmental / economic / social placeholders.
7. **Sources & evidence**: provenance and links.

Interactive features already work client-side: navigation, roof scenario buttons, hour slider, typology dropdown, sharing strategy, JSON **template** export. Do not regress these interactions. In the source, JS objects `roofData`, `profiles`, `strategies` and export payload are easy-to-find integration points. `profiles` are **illustrative normalized values**, not meters or simulator outputs.

**Implementation preference:** deliver a small, maintainable integration without wholesale framework churn. Either (a) a lightweight, local Python JSON/read-only server paired with existing HTML/JS, or (b) an already-established repository frontend framework if one exists at run time. At the observed HEAD, **no web frontend framework is committed in V2**. Use explicit API contracts and no arbitrary file path service. Existing Python dependencies should not be significantly destabilized. If a framework/library is introduced, explain why and pin/test it.

### Proposed API / JSON contracts (adjust to the repo, document actual schema)

- `GET /api/status`: stage statuses and version/commit; `last_updated_utc`; pending prerequisites.
- `GET /api/case-study/buildings`: public candidate inventory; `building_id`, typology, host flag, sources, verification states; avoid private data.
- `GET /api/roof/A160/scenarios`: two separate groups (`retrospective` and `additional`) of CSV-derived scenario rows, with `unit`, `confidence`, `source_url`, `data_origin`, `assumptions`.
- `GET /api/roof/A160/map?assessment=retrospective|additional&scenario=conservative|base|optimistic`: allowlisted GeoJSON eligible region and panel placements. Overlay observed PV only in comparison/reference context; never leak it into retrospective predictions.
- `GET /api/roof/A160/reference`: image-interpreted coverage, IoU, independent scoring limitations and dataset dates.
- `GET /api/models/office-surrogate`: existing `reports/simulation_surrogate/model_metrics.csv` and readiness summary, clearly labeling `training_origin=SIMULATED_PHYSICS` and `real_building_accuracy_validated=false`.
- `GET /api/pvgis/status`, `/api/demand/status`, `/api/sharing/status`, `/api/impact/status`: `state: pending` and `missing_inputs` until the relevant outputs exist; do **not** emit fake zeros for unknown results.
- `GET /api/evidence`: a safe public reference manifest with valid external URLs and version/source dates.

If the frontend is served statically without an API, a script can generate **allowlisted** JSON snapshots from these existing CSV/JSON files. The logic and provenance gates are the same. Never embed raw private material or allow `?path=../../...` file access.

For computed datasets later, require `data_origin`, `model_version` or `algorithm_version`, `source_url`/source report path, `source_date`/`capture_date`, `unit`, `timestamp_basis` (if temporal), and `confidence_or_limitations`. Use explicit `null` + a pending message rather than ambiguous zero.

---

## 4. Implementation work packages — run sequentially, with gates

### A0. Inspect and preserve the baseline (first)

- Pull current branch, inspect git status, create a feature branch; capture base SHA; do not discard uncommitted work.
- Read the current V2 `README.md`, `PIPELINE.md`, `docs/METHOD.md`, `docs/DATA_CONTRACTS.md`, `reports/NEXT_STEPS.md`, A160 rooftop report, and existing tests.
- Run the current local test suite before changing files: `python -m pytest -q` (or `.venv\Scripts\python.exe -m pytest -q` on Windows), and `python -m pipeline status`.
- Inspect `ui-template/index.html` and test all seven views in a browser. Capture baseline screenshots at desktop and mobile.
- Check for current UI work already in the repo and reuse it; **do not overwrite newer collaborator code**.
- Write `docs/ui_integration_baseline.md` with base SHA, baseline test results and pending backend datasets.

**Gate A0:** If tests fail or files conflict, keep the UI prototype intact, report the failure and proceed only with isolated, non-destructive steps.

### A1. Create the integrated UI shell (priority 1)

- Add the approved frontend in a clear folder such as `ui/` or `frontend/` (adapt to any framework already present). Preserve visual design, 7 views, keyboard navigation, screen-reader labels, responsive mobile layout and scenario controls.
- Add the minimal **read-only** API/snapshot generator described above. Source the building inventory from `datasets/inputs/case_study_candidates.csv` and the roof scenario metrics from the two actual processed CSVs, **not duplicated JS numeric literals**.
- Render current report evidence: estimated roof values, LiDAR/ortho dates, reference IoU, installed kWp **unknown**, provisional status, reported AI benchmark metrics.
- Keep the conceptual image labeled as such. Provide actual GIS polygon overlays **only** if projected/geo coordinates are displayed correctly; a schematic roof overlay with explicit 'not georeferenced' is acceptable as first pass.
- Apply user-friendly but scientifically meaningful empty states for PVGIS generation, real/mixed-use demand, computed sharing and impact.
- Keep the export button explicitly exporting a `UI_SCENARIO_TEMPLATE`, not a completed pipeline config or simulated result. Include selected roof assessment (retrospective/additional), user controls, provenance and `null` unfinished result fields.
- Document launch steps in `ui/README.md`, including local URLs, data reload procedure and offline operation.

**Gate A1 / acceptance:** all seven views render from a local run, selectors change the expected UI state, roof scenario numbers match committed CSVs, unknown kWp remains `null`, actual energy results are not fabricated, and a readable source/evidence drawer is functional.

### A2. QA, tests and evidence stability (priority 1)

- Add Python tests for API adapters: safe allowlisted file reads, correct units, data provenance, missing-file handling, no arbitrary paths, strict scenario names, empty outputs not fabricated.
- Add basic browser tests (existing Playwright script pattern is available in the bundle / local prototype): navigation, roof toggles, typology dropdown, slider, strategy selection, export JSON, narrow screens, source drawer, `null`/pending states. Avoid requiring external internet for routine CI.
- Verify keyboard focus order, escape/focus behavior for overlays, contrast and long text wrapping. Take desktop/mobile screenshots and place them under `ui/docs/`.
- Verify that existing `pipeline/models/` artifacts and `reports/simulation_surrogate/` results are unchanged; do not rerun full expensive EnergyPlus training simply to build the UI.

**Gate A2:** tests report actual pass/fail; documentation includes screenshots, base/working SHA and any failures. A PR/diff is reviewable without private dataset blobs.

### B. Existing A160 PV identification (priority 2, **data gate**)

- First search public architectural/MEP procurement and asset records for installed **module count, module Wp, inverter configuration, array azimuth/tilt and commissioning/version changes**. Record source URLs and dates. This is research; no unpublished actual inverter time series should be assumed.
- Existing 2025 image coverage (410.72 m²) and the 25 digitized row-block envelopes are **not a counted number of modules**, so do not infer verified kWp from these alone.
- If as-built data is absent: create **clearly assumed** low/base/high *existing-system hypotheses* only as exploration/uncertainty demonstrations, without setting `existing_capacity_verified=true`. Keep them out of the default energy-sharing calculation when strict validation does not permit them; present a pending verified path.
- Treat PVGIS generation of existing hardware and V1 *retrospective* theoretical roof potential as different roles. Do not combine or double-count. Extra 0–1.26 kWp is separate and contingent, not the project's principal generation resource.
- Output a dated installation-source register and specific unresolved assumptions; do not silently invent specs.

**Gate B:** no verified installed capacity ⇒ no “measured PV generation” or authoritative community savings. Stop/mark missing evidence rather than changing backend safety checks.

### C. PVGIS hourly generation (priority 3, when inputs permit)

- Choose and record PVGIS dataset/weather period, observed/assumed installed power, losses, azimuth, tilt, source URL, timestamp semantics and any module-level aggregation assumptions.
- Export hourly PVGIS series and use existing `pipeline/step_03_pvgis/importer.py`. Correctly convert W/kW to kWh for a one-hour interval; retain PVGIS minute offsets and validate exact hourly index.
- Treat PVGIS as a physics **model**, not measured plant data. `energy_sharing_eligible` rules must remain intact. If using an exploratory unverified-system scenario for a classroom demonstration, maintain a separate tagged sandbox assessment and **do not** promote it into verified study results.
- Implement the UI's solar graph only after an actual exported series exists, with metadata and sensitivity ranges.

### D. A160 + mixed-typology demand preparation (priority 3; substantial research task)

- Preserve the already trained EnergyPlus→XGBoost office route. Build or adapt an appropriate A160 office EnergyPlus geometry + schedule domain; use published area definitions cautiously and document envelope/HVAC assumptions.
- For ITAEB, 18 homes and NH hotel, use **appropriate education/residential/hotel EnergyPlus archetypes** and sourced schedules, or explicit synthetic demand until a validated model exists. Never run the small-office XGBoost directly on these typologies.
- Choose one representative-year/weather basis, resolve local calendar vs UTC/DST and PVGIS minute offsets, validate 8,760-hour or explicitly leap-year conventions, check all buildings have matching time indices.
- If the AI surrogate is expanded: split by whole new archetypes/configurations or suitable out-of-domain holdouts, compare against baseline and independent simulator reference; report extrapolation failures and not only positive improvements.
- Frontend should render demand as `SIMULATED_PHYSICS` or `ML_PREDICTION` (as appropriate), never `OBSERVED_METER` without an actual meter source.

### E. Sharing comparison + safeguards (priority 4, **model/test gate**)

- Use existing deterministic `step_07_energy_balance` on the *same hourly PV and demand inputs* across `grid_only`, `host_only`, `fixed_equal_shares`, and `demand_informed_preagreed` scenarios.
- Forecast-derived hourly coefficients must be fixed **before** evaluating on independent reference loads; evaluating a plan on the same forecast it used is a planning demonstration, **not** evidence of AI improvement.
- Keep coefficients normalized and nonnegative, respect the agreed hourly allocation concept; no live energy trading.
- Verify conservation: `demand = solar_used + grid_import`; `pv_allocated = solar_used + unconsumed_allocated_pv`; total shares sum to one per hour; PV power never appears from nowhere.
- **Crucial failure case:** if the host already absorbs all PV, collective sharing cannot increase total local PV self-consumption or lower overall grid imports, though it can redistribute private bill benefits. Some allocation scenarios can perform worse than host-only; show that honestly.
- Distinguish final PV that is potentially exported from allocation accounting and avoid double-counted benefits, billing and emissions.

### F. Impacts and AEC interface upgrade (priority 5)

- Calculate environmental, economic and participant-benefit proxies only with **dated, sourced** price/emissions/cost inputs in `config/impact_assumptions.json` and documented boundary conditions. Its numerical assumptions are currently all `null`.
- Social fairness must be defined explicitly (e.g., variation in participant benefit relative to allocated solar/consumption). Do not imply access equity or residents' vulnerability without data and consent.
- Consider a later genuine architectural 3D map (Rhino/Three.js or georeferenced mesh); it is a **separate** step from integrating backend data into the approved conceptual image.
- Provide current status, uncertainty badges/labels, and comparisons rather than a polished but unsubstantiated “success” dashboard.

---

## 5. UI behavior checklist and definition of done

**When UI integration is considered successful:**

- [ ] A branch/diff/PR with a locally runnable UI and documented commands exists.
- [ ] All seven prototype sections remain reachable, responsive and accessible.
- [ ] A160 geometry/capacity cards load from repository CSV/JSON, rather than manually copied UI constants.
- [ ] Retrospective potential, additional potential and observed existing PV are represented as **three separate concepts**.
- [ ] The existing installation's kWp remains **unknown/null** unless a verifiable source is linked.
- [ ] A160 rooftop confidence and LiDAR/orthophoto capture dates are visible.
- [ ] The 2015 Barcelona solar map record is explicitly a **legacy comparison**, not modern A160 ground truth.
- [ ] The mixed-use candidate inventory shows host, typology, what is known, and what is assumed; no claim of confirmed regulatory eligibility.
- [ ] XGBoost metric and real-building limitation are labeled clearly; curves remain illustrative until generated data exists.
- [ ] Solar/sharing/impact screens handle pending datasets without invented numerical values.
- [ ] UI scenario export remains an unexecuted, reproducible template with provenance.
- [ ] Python tests and browser smoke tests pass (or failures explicitly logged).
- [ ] No trained artifacts, V1 source, source provenance or historic benchmarks were overwritten.
- [ ] Completion summary contains changed files, screenshots, tests, exact blockers and next decisions for the user.

**Nice to have (not required in first pass):** interactive 2D roof GeoJSON layer controls, per-metric source drawer, light comparison chart between observed image mask and hypothetical predicted panels, clickable source links, CSV download for view datasets.

**Deferred by default:** a working 3D parcel model, new CV training, new building-measurement acquisition, full mixed-use AI, live PVGIS API, full tariff/billing treatment, legal certification, electricity control. Do not rush these into the same code change.

---

## 6. Conversation takeaways from today's research / design discussion

1. **Do not restart the technical pipeline.** It is intact, with V1 roof processing successfully migrated into V2, trained office-surrogate models preserved, and the A160 first milestone complete as a low-confidence screening.
2. **A160 stays the primary host** despite only 0–1.26 kWp of conditional *additional* space on the dominant upper roof, because **existing PV** is now the planned solar resource to evaluate.
3. **Retrospective vs operational**: The 95–117 kWp figures measure hypothetical geometric potential; they are not an as-built statement. Existing PV area is visible, but system kWp is unknown. The image reference can compare spatial layout, not installed capacity or maximum technical feasibility.
4. **One roof / mixed uses:** ITAEB school, 18 municipal homes, and NH hotel were chosen to introduce schedule diversity (classes vs evenings/weekends vs 24-hour activity). No private demand data is public; all use patterns currently require documented simulation assumptions.
5. **AI role is specific:** the selected trained XGBoost is an EnergyPlus emulator for *one* office reference model. ML improvements on simulated configurations do not imply real A160 accuracy. The earlier real-meter BDG2 XGBoost failed to beat the simpler hour-of-week method; preserve that negative result.
6. **One existing tool does not replace another:** Catastro/ICGC/LiDAR/V1 answer spatial feasibility; Barcelona solar atlas offers historical context; PVGIS answers hourly modeled generation; EnergyPlus simulates electricity use; ML emulates simulations; deterministic accounting checks energy sharing; the UI communicates evidence.
7. **Visual language approved:** edited Poblenou/chamfered-block architecture, dark-green navigation, blue arrays and yellow connections. Do not present a watercolor illustration as an exact map of the A160 block.
8. **UI prototype is approved as a visual starting point:** seven-page standalone HTML with basic interactions; next task is **honest data integration**, not new graphic generation. The latest professor-facing presentation and UI assets are independent from backend model code.
9. **Conservation before persuasion:** the project's claim is not that a community *always* saves energy; its research contribution is determining **when** rooftop electricity sharing is useful, when it is neutral, and when it is worse than host-only.
10. **Development structure:** finish an evidence-rich first integration milestone, then do verified existing PV → PVGIS → site-appropriate building simulations → held-out demand test → allocation → sourced impacts → optional real 3D view.

### Energy-conservation takeaways (the physics / accounting rules)

- **Do not create electricity via allocation:** the same generation time series must be used for all sharing scenarios.
- **No solar at night without storage:** a residential evening peak does not automatically make midday PV more useful. Do not imply battery storage exists.
- **Each hour's demand must reconcile:** `demand_kwh = used_pv_kwh + grid_import_kwh` under the simplified no-storage demand accounting.
- **Each hour's assigned solar must reconcile:** `allocated_pv_kwh = used_pv_kwh + unconsumed_allocated_pv_kwh`, with physically coherent allocation coefficients.
- **More consumers ≠ more total PV consumption:** if A160 already uses all the electricity, added neighbors cannot increase whole-cluster self-consumption in a no-storage accounting case; they may change who pays for/benefits from it.
- **Reallocation is not generation:** an economic distributional benefit should not be counted as avoided emissions if grid imports do not change.
- **Solar-map estimates and roof-layout estimates are alternate comparisons, never additive PV capacity.** Retrospective existing roofs and incremental extra panels are separate supply cases; do not double-count.
- **Sustainability claims require boundaries:** grid-emissions factors, tariff structures, export treatment, PV embodied carbon, capital costs and social proxies have different assumptions. Clearly label what has and has not been evaluated.

---

## 7. Results summary Codex should hand back to the user

On finishing each bounded milestone, provide:

1. **What changed:** branch/commit/PR link (or exact patch location), frontend/backend files modified, screen previews.
2. **What actually ran:** commands and passing/failing test counts, optional browser screenshot paths, baseline comparison.
3. **What is newly connected:** real report/CSV/GeoJSON sources by relative path and their visible status in the UI.
4. **What is not finished:** missing PV specifications, unmet simulation assumptions, missing public source data, legal/engineering constraints.
5. **Any scientific change:** reported metrics, provenance or data-origin distinctions altered and justification (otherwise explicitly say none).
6. **Next smallest reviewable task:** ideally as one branch/PR, not a vague claim of a completed energy community.

If useful, update `reports/NEXT_STEPS.md` and `ui/README.md` **after** verified work. Do not write a success report before running tests. Do not schedule future tasks or claim unattended execution is active unless a real Codex run has been started.

---

## 8. Key research, software and architectural sources (live URLs)

**Code and direct reports**

- V2 repo: <https://github.com/SindhujaDavuluri/rooftops_repowered_v2>
- V1 repo: <https://github.com/iaac-maai/Rooftops_RePowered_OperableFutures2026_Team1>
- A160 roof report: <https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/README.md>
- AI model evaluation: <https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/simulation_surrogate/model_metrics.csv>
- Data contracts: <https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/docs/DATA_CONTRACTS.md>
- Development pipeline: <https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/PIPELINE.md>

**Physical site and community**

- A160 architecture: <https://www.batlleiroig.com/en/projects/oficines-almogavers-160-a-barcelona/>
- ITAEB: <https://agora.xtec.cat/ins-itaeb/>
- Ciutat de Granada housing: <https://www.consorcihabitatge.barcelona/es/noticias/el-imhab-entrega-las-llaves-de-18-pisos-de-alquiler-social-en-el-barrio-del-parc-i-la-llacuna-del-poblenou-1405102>
- NH hotel: <https://www.nh-hotels.com/en/hotel/nh-barcelona-diagonal-poblenou>

**Data and methods**

- Barcelona rooftop energy map: <https://coneixement-eu.bcn.cat/mapaEnergia/viewer.html>
- European Commission PVGIS: <https://photovoltaic-geographic-information-system.ec.europa.eu/>
- ICGC orthophoto and LiDAR services: <https://www.icgc.cat/>
- EnergyPlus: <https://energyplus.net/>
- Building Data Genome 2: <https://doi.org/10.1038/s41597-020-00712-x>
- XGBoost: <https://xgboost.readthedocs.io/>

*End of handover. Use the accompanying Codex launch prompt to start the bounded integration run.*
