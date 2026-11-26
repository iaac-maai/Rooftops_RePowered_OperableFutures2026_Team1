# A160 rooftop feasibility: first development milestone

Completed 2026-11-15 as a **low-confidence geometric screening**, with two separate assessments. This is not installation approval, a verified maximum-capacity study, an existing-PV capacity measurement or a completed energy-community pipeline.

Open [the annotated rooftop figure](A160_two_assessments.png), [its PDF](A160_two_assessments.pdf) and [the newest-imagery comparison](A160_latest_imagery_comparison.png).

## Results

Assumed new module: 1.76 × 1.13 m, 420 Wp; tilt 10°; roof-aligned facing direction 135.8935° clockwise from north, equivalent to **PVGIS aspect −44.1065°**. These are design assumptions, not measurements of installed A160 modules. Scenario setbacks/obstacle clearances are 2/1 m, 1/0.5 m and 0.5/0.3 m. They are sensitivity assumptions, not statutory clearances.

| Assessment | Conservative | Base | Optimistic |
| --- | ---: | ---: | ---: |
| A: retrospective predicted module count | 227 | 264 | 278 |
| A: retrospective geometric potential, kWp | 95.34 | 110.88 | 116.76 |
| A: horizontal projected panel coverage, m² | 444.60 | 517.07 | 544.49 |
| B: additional candidate module count | 0 | 3 | 3 |
| B: conditional additional capacity, kWp | 0.00 | 1.26 | 1.26 |
| B: eligible residual area before panel packing, m² | 7.99 | 28.52 | 41.97 |

**Confidence is low for all scenarios.** The spread is a parameter sensitivity range, not a statistical confidence interval. Only the dominant high roof is assessed. Lower terraces and secondary service roofs are excluded from this milestone; their exclusion does not prove they can never accommodate PV. The three additional candidates require verification of plant access, maintenance/safety space, shading, mounting and roof structure. Small registration or clearance changes can remove them; zero additional capacity remains plausible.

Full results and mapped geometries are in [assessment A](../../../datasets/processed/roof_capacity/A160/retrospective/) and [assessment B](../../../datasets/processed/roof_capacity/A160/additional/). Each has three scenario GeoJSON layers, SVG previews, a CSV and a source/parameter manifest. Calculations use EPSG:25831 metres; GeoJSON uses WGS84.

## Host identification and sources

- **Cadastral reference 2635601DF3823F**, building footprint 1,718.03 m². Published address Almogàvers 160 falls within the official cadastral street range **CL ALMOGAVERS 154 N2-164**. Identification joins the official building/address data, the developer's published location/site plan and the visible modern roof. Footprint area is not usable roof area or conditioned floor area. The original street-number geocoder failed; its cached diagnostic is not the final identity result.
- Official building geometry: the existing Barcelona INSPIRE GML download under `datasets/raw/cadastre_barcelona/`. Official parcel response: [Catastro DNPRC](https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPRC?Provincia=BARCELONA&Municipio=BARCELONA&RefCat=2635601DF3823F). Developer context: [Batlleiroig project](https://www.batlleiroig.com/en/projects/oficines-almogavers-160-a-barcelona/). Cached responses and selection evidence remain in `datasets/raw/roof_capacity/A160/source_probes/` and `cadastre_candidates.json`.
- **Latest finalized ortho: 2025-06-18**, native GSD 0.25 m, ICGC `ortofoto_color_2025` / current finalized layer. The downloaded display is resampled to roughly 0.10 m; that does not create 0.10 m source accuracy. A 2022-05-18 image already shows PV.
- **Newest public provisional image: 2026-03-16**, ICGC `ortofoto_color_provisional`, obtained and visually checked. It shows the existing array blocks, but roof alignment differs and its native GSD was not established from the feature-info response. It is retained as current visual context; no unregistered label transfer or survey-grade change claim is made. [Capture checks](latest_imagery_check.json).
- **LiDAR acquired 2022-06-01**, ICGC current public tile `432583`, EPSG:25831, LAS 1.4. File creation is 2025-08-08, **not** the acquisition date. Acquisition was recovered from LAS adjusted-standard GPS timestamps, with the post-2017 GPS−UTC offset. [Acquisition evidence](lidar_acquisition.json). Classified roof coverage is about 92.5%. The full 303 MB LAZ and a 45,550-point footprint clip are retained locally.
- [ICGC imagery service](https://geoserveis.icgc.cat/servei/catalunya/orto-territorial/wms?SERVICE=WMS&REQUEST=GetCapabilities), [public LiDAR tile](https://datacloud.icgc.cat/datacloud/lidar-territorial/vigent/laz_unzip/full10km4358/lidar-territorial-full1km432583.laz). URL, retrieval status, cached response and SHA256 evidence are recorded in the source JSON files and `source_register.json` beside this report.

## A: retrospective validation against an existing installation

The V1 grid/flat-plane/obstacle and panel-packing logic is reused. A dominant-plane structural approximation absorbs shallow relief within a fixed ±0.45 m band; higher relief remains an obstacle. The predictor receives footprint, classified LiDAR and design parameters. It receives **no observed PV mask, image-derived array envelope, current access annotation or manually drawn current roof boundary**. Imagery is added to previews after geometry/panel packing. Prediction is frozen before reference scoring; input/parameter changes require an explicit rebuild.

PV already existed before the June 2022 flight. Consequently, there is **no clean pre-installation LiDAR** in this dataset. The height band reduces false panel obstacles, but may also suppress low equipment and cannot reconstruct hidden bare-roof elevations with certainty. This is computational reference separation, not a blinded human experiment or an independent pre-installation validation. Structural parameters were not optimized against the reference metrics.

The user confirmed PV identity in the 2025 ortho. Reference annotation independently delineates visible row-block regions, then estimates dark module-like pixel coverage. The 25 annotated row blocks are **not module counts**. The projected reference coverage is **410.72 m²**, with threshold sensitivity **350.35–447.97 m²**; this is not a calibrated confidence interval. Delineation, shadow and registration add uncertainty. Observed module count, module Wp and installed kWp remain unknown.

| Agreement metric | Conservative | Base | Optimistic |
| --- | ---: | ---: | ---: |
| Predicted-panel / image-reference area IoU | 0.271 | 0.265 | 0.258 |
| Reference area within predicted eligible roof | 78.4% | 82.4% | 83.6% |
| Predicted projected area minus reference coverage | +8.3% | +25.9% | +32.6% |

These results indicate limited placement agreement. They do not validate the layout as installed, prove a maximum, or justify substituting assumed 420 Wp modules for actual installed capacity. See [metrics](retrospective_validation.csv) and [reference separation](reference_separation.json). The low IoU is retained openly; the model has not been tuned to reproduce the installation.

## B: current additional PV

Existing PV row-block **envelopes**, including their internal spacing, are occupied infrastructure. B uses frozen A geometry, intersects a separately image-interpreted current high-roof boundary, and subtracts array envelopes plus scenario clearances and explicit access/plant exclusions. A provisional 2 m visible perimeter circulation reserve is a stated assumption. These current-condition annotations are used only in B. Already installed and proposed panel areas are not counted twice.

The quantitative masks refer to finalized 2025 imagery; provisional March 2026 imagery provides a newer visual check, not registered replacement geometry. Additional potential remains conditional until the actual roof/access plan is checked.

## Municipal comparison

The [Barcelona energy map](https://coneixement-eu.bcn.cat/mapaEnergia/viewer.html) public CARTO `fotovoltaica` table was accessible without credentials. One polygon is associated by its representative point inside the cadastral building: record **99036**, potential **103.5 kW**, usable area **1,094.8 m²**, modeled generation **129,323.2 kWh/year**. The raw source is retained.

Its created/updated fields are **2015-03-12**, predating the modern 2022 host. These are record dates, not established survey dates. This is a legacy geometry association, not a verified parcel installation record. Numerical similarity to A's base scenario does not validate modern A160. City potential is never added to V2 capacity. [Comparison CSV](../../../datasets/processed/roof_capacity/A160/municipal_map_comparison.csv).

## PVGIS and what remains needed

[PVGIS inputs](../../../datasets/inputs/roof_capacity/pvgis/A160_pvgis_inputs.csv) and seven individual JSON records separate three counterfactual A scenarios, three incremental B scenarios and the existing installation with **null capacity**. Coordinates, estimated kWp, assumed tilt and correctly converted aspect are supplied. Weather period and system losses are deliberately unset. The zero-capacity scenario must skip simulation. Select one scenario at a time; do not sum them.

Retrospective output is for counterfactual validation only and cannot stand in for existing generation. B represents additional proposed generation only. The case-study importer rejects these provisional/retrospective records for energy accounting. No PVGIS yield was fabricated, no host generation was inserted into the energy balance and no demand model was retrained.

**No manual PVGIS or municipal-map export is needed to complete this geometry milestone.** For the next yield stage, select PVGIS weather years/database and system losses, then export hourly CSV with its settings/time basis. A newer municipal parcel report would improve comparison if available. Existing generation requires actual module count/Wp/orientation/tilt or a verified installation record. An as-built access/plant/PV plan would resolve the small additional candidates and improve reference measurements.

## Reproduce

From the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pipeline roof-feasibility
.\.venv\Scripts\python.exe -m pytest -q
```

The first command is offline with cached data and reuses frozen A predictions after checking source/parameter hashes. It regenerates the reference, B, validation, municipal comparison, figures, PVGIS handoffs and readiness report only. To deliberately regenerate A before reference annotation, add `--rebuild-prediction`; preserve earlier outputs if comparing versions. LiDAR can be downloaded/reclipped with `python -m pipeline.step_02_roof_capacity.download_lidar`; imagery currency can be checked with `python -m pipeline.step_02_roof_capacity.latest_imagery` (network required). Refreshing sources requires review of capture dates/registration before reuse.

V1 code attribution and original hashes are in `pipeline/step_02_roof_capacity/V1_PROVENANCE.json`. No trained roof-vision checkpoint was found in V1; the copied optional architecture is not trained or used. All eight existing demand artifacts retain their original SHA256 and load after folder migration. The disposable Chicago-reference inference input/predictions/check were removed; the legitimate simulation reference, 36 configurations, model features/weather and model artifacts are retained because they support the working demand surrogate.
