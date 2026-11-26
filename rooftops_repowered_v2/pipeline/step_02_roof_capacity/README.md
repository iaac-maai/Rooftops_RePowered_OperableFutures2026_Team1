# Step 02 — Roof capacity from V1

Copied and adapted from the user's local `research_studio_team_1` checkout.
`V1_PROVENANCE.json` records attribution, source revision and original hashes.
The V1 checkout is read-only and unchanged.

## Active A160 dual assessment

```powershell
.\.venv\Scripts\python.exe -m pipeline roof-feasibility
```

This is the current rooftop-only entry point. Read [the milestone report](../../reports/roof_capacity/A160/README.md)
for results, source dates, visualizations, confidence, municipal comparison and
remaining data needs. The demand surrogate is unchanged.

- `assessments.py`: LiDAR-only dominant-plane retrospective prediction, frozen
  input/parameter checks, additional-capacity subtraction and reference metrics.
- `reference.py`: independent 2025 image-reference digitization and current
  occupied-array/access/roof-boundary annotations. Only B consumes current masks.
- `milestone.py`: offline orchestration and role-separated PVGIS inputs; no demand
  training, yield simulation or energy-community evaluation.
- `figures.py`: annotated scientific PNG/PDF and finalized/provisional comparison.
- `download_lidar.py`, `latest_imagery.py`: public-data acquisition/date evidence.

Actual configuration is `config/a160_assessments.json`; manual annotation rules
are in `config/a160_pv_reference_annotation.json`. Outputs are separately stored
under `datasets/processed/roof_capacity/A160/retrospective/` and `additional/`.
PVGIS records live in `datasets/inputs/roof_capacity/pvgis/`. Reference GeoJSONs
and their provenance are under `datasets/inputs/roof_capacity/`.

The 2022 flight already contains installed PV. A's fixed low-relief structural
approximation receives no observed mask, but is not verified pre-installation
geometry. The user-confirmed 2025 image supplies the quantitative reference;
the newer provisional 2026 image is visual context with registration uncertainty.
Observed installed count/kWp remain unknown. B excludes existing array envelopes
and assumed access space. No capacity scenario is a maximum or installation approval.

The strict generic adapter described below remains available for future reviewed
cases. Its unfilled masks/year-only completion gates are deliberately not used
to claim A160 has clean pre-installation data. Do not run its blocked workflow in
place of `roof-feasibility` for the current milestone.

## Reused components

- `catastro.py`, `geocode.py`: public building identification; V2 caches replies
  and treats results as candidates. It refuses a largest-building guess and
  bounds the search to Barcelona to reject same-named streets in other towns.
- `grid.py`, `lidar_tiles.py`, `lidar_roof.py`: projected raster geometry, class
  6/77 roof points, flat-plane growing, obstacle masks, lower-level exclusions.
- `layout.py`: configurable module dimensions/Wp, tilt, orientation, row spacing,
  setbacks and grid shifts. Panels are packed separately on detected roof planes
  so a panel cannot bridge adjacent levels of a stepped roof.
- `ortho.py`: optional orthophoto acquisition/QA support. A latest-layer label
  does not prove the underlying image acquisition date.
- `municipal_map.py`: independent municipal potential-map parsing/aggregation.
  The V1 website and batch entry points are not imported.
- `vision_model.py`: optional four-channel RGB+height U-Net/ResNet34 definition.
  **No trained checkpoint was found or copied.** No PyTorch stack was installed,
  no CV model was trained and no CV prediction is used by the capacity command.

V1 shading/yield and community-demand code are not reused here: V2's PVGIS and
EnergyPlus demand/accounting modules remain responsible for those stages.

## Generic strict workflow (not the active A160 dual assessment)

```powershell
.\.venv\Scripts\python.exe -m pipeline roof-fetch-building
.\.venv\Scripts\python.exe -m pipeline roof-capacity
.\.venv\Scripts\python.exe -m pipeline roof-pvgis-settings --scenario base
```

Edit `config/roof_capacity.json` to supply the **real** A160 data. Acquisition can
only create an unverified cadastral candidate; it never enables geometry QA.
For the actual calculation supply:

1. The current A160 footprint and explicit CRS, visually checked against post-
   construction plans/imagery; only then set `geometry_verified_current`.
2. A reviewed eligible-roof polygon and explicit exclusion layer. Empty GeoJSON
   exclusions are acceptable only after verifying there are no applicable objects.
   Exclude gardens, terraces, public access, equipment, safety paths and existing PV.
3. A dated review source. `review.source_date` means the **capture/as-built source
   date**, not today's review/download date. Verify existing PV as absent or masked.
4. For LiDAR: copy `datasets/inputs/roof_capacity/lidar_tiles_TEMPLATE.csv` to
   `lidar_tiles.csv`; fill paths, per-tile flight start/end, source URL, CRS, vertical
   units and acquisition evidence. File creation dates are not survey dates.
5. Review module/design assumptions. V1's 420 Wp module and buffers are illustrative
   geometric assumptions, not a selected product or statutory fire/safety design.

A160 completion is currently known only to 2022. Until an exact completion date is
supported, flights/source imagery during 2022 are ambiguous and rejected; accept
post-2022 data or provide a verified exact completion date. Every tile must meet
the vintage gate. LAS CRS is checked against the declared EPSG:25831 where present.
LAZ files are streamed in chunks. Insufficient classified roof coverage blocks.

If LiDAR predates the modern building, select `method: reviewed_plan` with current
reviewed plans/imagery and explicitly limited confidence. It still requires the
same eligible/exclusion and existing-PV checks. Separate roof levels must be
expressed as disjoint eligible regions; do not flatten a step into one usable plane.

## Outputs and PVGIS handoff

Success writes under `datasets/processed/roof_capacity/A160/`:

- `roof_capacity_scenarios.csv`: conservative/base/optimistic usable area, module
  count, Wp/module, estimated kWp, buffers, source date, provenance and confidence.
- `<scenario>_eligible_roof.geojson`, `_obstacles.geojson`, `_panels.geojson`:
  WGS84 exports. Calculations remain in EPSG:25831 metres.
- `<scenario>_qa.svg`: roof/mask/panel overlay; optional orthophoto background needs
  an explicit image extent. It is not a substitute for a human as-built check.
- `<scenario>_lidar_reading.json`: surfaces, heights, coverage and obstacles for QA.

`reports/roof_capacity/A160/readiness.json` records ready/blocked status, source
hashes, CRS and limitations. A blocked run emits **no invented capacity CSV**.
Zero capacity from a fully excluded roof cannot generate positive PVGIS settings.
Changing settings invalidates the prior ready result.

`roof-pvgis-settings` converts the selected count-based kWp to an explicit settings
record and converts north-clockwise azimuth to PVGIS south-zero (east=-90,
west=90). Weather year and system losses remain unset until deliberately chosen.
PVGIS provides energy yield; this stage provides **estimated geometric capacity**.

For a separately dated municipal comparison:

```powershell
.\.venv\Scripts\python.exe -m pipeline roof-compare-map --input YOUR_CITY_EXPORT.geojson --source-date YYYY-MM-DD --source-url YOUR_SOURCE
```

The municipal number is reported alongside, never added to our scenario capacity.
Legacy imagery/centroid matches do not establish modern A160 roof geometry.
No structural, waterproofing, permitting, grid-connection or safety approval is implied.
