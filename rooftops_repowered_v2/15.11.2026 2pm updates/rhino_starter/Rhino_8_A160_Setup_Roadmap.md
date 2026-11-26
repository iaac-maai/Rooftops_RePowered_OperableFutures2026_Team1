# A160 / Rhino 8 → Honeybee → EnergyPlus: preparation roadmap

**Status:** planning-only, 15 November 2026. **No A160 `.3dm`, Grasshopper `.gh`, official city DWG or A160 EnergyPlus run has been created or verified.** The project is paused; do not execute this workflow until the next session.

## What to obtain on the Windows workstation

| Resource | Official download | Purpose and caution |
|---|---|---|
| Licensed **Rhinoceros 8** with Grasshopper | https://www.rhino3d.com/download/ | Geometry authoring and checks; license belongs to user |
| **Ladybug Tools for Grasshopper** 1.10 family; includes Honeybee Energy | https://github.com/ladybug-tools/lbt-grasshopper/releases | Confirm Rhino 8 compatibility in installed release; test components and OpenStudio/EnergyPlus recipe; do not overwrite V2's portable engine blindly |
| **Barcelona 2026 3D buildings CAD/DWG** | https://portaldades.ajuntament.barcelona.cat/mapes/146 | Find **DWG 3D (el Parc i la Llacuna del Poblenou)**. Dataset dated 26 May 2026, CC BY 4.0. Download only this neighborhood initially; verify A160 is present and geometry up to date. Interactive map alternative: https://w20.bcn.cat/cartobcn/?prod=146 |
| A160 architects’ facts, plans, roof context | https://www.batlleiroig.com/en/projects/oficines-almogavers-160-a-barcelona/ and https://www.conrentramway.com/portfolio/a160/ | Test building identity and floor elevations; construction area ≠ conditioned area |
| Official footprint / roof reference | https://github.com/SindhujaDavuluri/rooftops_repowered_v2/blob/main/reports/roof_capacity/A160/README.md | Catastro ref **2635601DF3823F**; ICGC LiDAR and 2025 ortho. Post-installation LiDAR contains PV; do not treat it as a bare-roof survey |
| **Barcelona weather file** (EPW) | Existing `datasets/raw/simulation_weather/` within the local V2 workspace, or weather acquisition through Ladybug Tools. | Record whether EPW is IWEC typical meteorological year or a real historical year. Do **not** conflate with PVGIS **2017 SARAH3** or synthetic local-standard 2017 schedules |
| Reference building models (optional comparison only) | https://www.energycodes.gov/prototype-building-models | U.S. archetypes are methodological starting points, not A160 local calibration |

**Compatibility:** Rhino 8 officially supports opening/importing DWG. The Honeybee `Model to OSM` component can produce Honeybee JSON, OSM, IDF and, with a run toggle, EnergyPlus outputs. Sources: https://docs.mcneel.com/rhino/8/help/en-us/fileio/autocad_dwg_dxf_import_export.htm and https://docs.ladybug.tools/hb-energy-primer/components/5_simulate/model_to_osm . Actual plugin installation on the user's workstation is unverified.

## Start from the city model, not from a guessed building

1. Before modifying the imported drawing, record file URL, download date, file SHA256, coordinate reference system, original units, layers, known level-of-detail and any supplied metadata. The **2026 edition of the city dataset does not itself certify the building is measured in 2026**.
2. Open Rhino 8 → **File → Import** the municipal DWG. Inspect import report, file **Units** and object bounding extents. Rhino DWG read support is documented up to AutoCAD 2018 file format; if conversion is needed, document who converted it and preserve the original.
3. Isolate **Carrer dels Almogàvers 160**, checking the cadastral building footprint **2635601DF3823F** and the Batlleiroig architecture images against the DWG. Do not confuse A160 with **Almogàvers 165** or older city-block structures.
4. Retain an untouched source layer called `00_SOURCE_DWG_LOCKED`. Make a separate versioned `.3dm` working file. Record the source coordinate offset if geometry is shifted near `(0,0,0)` for modeling; preserve reversibility to metric **EPSG:25831** or the confirmed original CRS.
5. Isolate neighborhood massing in `01_CONTEXT_SHADING`. Buildings used only as shade context are **not** automatically thermal zones or energy consumers.
6. Clean and verify the A160 external massing, face normals, roof levels, window openings and courtyard/terrace edges. Compare to official footprint and image evidence. Save comparison screenshots. The public massing probably lacks an accurate interior plan, so floor heights/internal layouts must be explicit **hypotheses** unless as-built plans support them.
7. Convert to closed thermal volumes for ground+five floors or the confirmed floor scheme; group rooms by reasonably distinct schedules/HVAC, e.g. perimeter/core and ground services. **Do not assign 9,400 m² as measured conditioned area**—this is a published office-area figure, distinct from modeled conditioned area.
8. Add plausible windows and shading surfaces, keeping assumptions separate: `05_GLAZING`, `04_THERMAL_ZONES`, `06_ROOF_PV_REFERENCE`. Existing roof PV is a visual contextual layer, **not** an installed kWp input.
9. Each thermal room should have a stable `zone_id`, `floor_id`, `room_use`, `geometry_provenance`, and an area/volume verified by geometry checks. Use the accompanying `thermal_zone_inventory_TEMPLATE.csv` before any simulation.
10. Build a **small A160 test model first** (one/few zones and a one-week or design-day smoke run), then a defensible full-year model once all geometric/topological checks pass. Preserve all raw outputs and log files.

## Honeybee → EnergyPlus setup

1. Open Grasshopper in Rhino. Verify Ladybug/Honeybee Energy components load and version strings; if missing, stop with a clear environment checklist. Test a single boxed thermal room before attempting A160.
2. Make Honeybee Room objects from **closed, planar, valid Breps**; `Solve Adjacency`, check external vs interior vs ground surfaces, make correct aperture/shade objects, ensure no duplicated faces.
3. Assign **sourced or explicitly synthetic** envelopes, glazing, infiltration, occupancy, lighting, plug loads, ventilation and electric HVAC. Use `energyplus_scenario_parameters.csv` only as a starting hypothesis. Record heating fuel/electricity boundary; do not mislabel ideal thermal loads as facility electricity.
4. Attach a named, sourced **EPW** and a documented calendar/day-type mapping. Select one common weather strategy for later PV and demand matching. PVGIS 2017 :10 UTC samples and original IWEC standardized 2017 are **not aligned** by default.
5. `HB Model to OSM` → create Honeybee JSON/OSM/IDF and run EnergyPlus. Preserve `.3dm`, `.gh`, `.hbjson`, `.osm`, `.idf`, `.epw`, `eplusout.err`, output CSV/SQL and scenario hashes.
6. Requested primary target: `Electricity:Facility [J](Hourly)` converted to `electricity_kwh = J / 3,600,000`. Preserve raw hour-ending labels 01:00–24:00; map them carefully to interval-start timestamps and a documented timezone. Use explicit UTC instants only after validated conversion.
7. Do not train XGBoost until **8760 valid hourly facility-electricity samples** for the chosen non-leap reference calendar, no fatal errors, plausible annual/end-use output, geometry QA and a hold-out strategy are available.

## Proposed Rhino layers

`00_SOURCE_DWG_LOCKED`; `01_CONTEXT_SHADING`; `02_A160_MASSING`; `03_FLOOR_DATUMS`; `04_THERMAL_ZONES`; `05_WINDOWS_APERTURES`; `06_ROOF_PV_REFERENCE`; `07_COURTYARDS_TERRACES`; `80_QA_DIMENSIONS`; `90_METADATA`.

A **proposed** layer-creation script `create_rhino_layers_STARTER.py` is included as a future convenience. It only creates layers, not building geometry. Nothing in this package should be executed by Codex during the current pause.

## Minimal acceptance criteria for a first real A160 model

- Exact building identity and geometry source evidenced and reproducible.
- Source coordinate units and georeference clearly documented.
- Closed, non-overlapping thermal rooms with reported areas and facade orientation.
- Roof/terraces model distinguished from existing-PV and PV potential analysis.
- Assigned building-use and HVAC/envelope assumptions tied to source IDs or explicit hypotheses.
- EnergyPlus annual output and eplusout.err inspected; `Electricity:Facility` exists, 8760 valid hours, finite nonnegative load.
- Compare annual intensity against literature proxies **without fitting the model to them**.
- Save source and model hashes. Preserve existing `pipeline/models/` artifacts.

**Future outputs, not present yet:** `A160_geometry_review.3dm`, `A160_honeybee.gh`, `A160_hb_model.hbjson`, `A160_model.idf`, `A160_energyplus_hourly.csv`, simulation QA and new XGBoost `.joblib` if validation succeeds.
