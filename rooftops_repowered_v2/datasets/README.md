# Rooftops RePowered V2 datasets

Raw downloads retain the publishers' original formats. These are research inputs,
not verified case-study measurements. No API keys are used.

Trained models and fitted baselines belong in `pipeline/models/` relative to the
project root, separate from this dataset directory. This location supersedes
the model-output paths in the original handoff document.

## Core downloads

Run `..\.venv\Scripts\python.exe ..\download_datasets.py` from this directory.
The downloader reuses validated existing CSVs, resolves Git LFS files, and records
failures instead of treating error responses as data. Use `--only SOURCE_ID` to retry
selected sources. Python's standard library and `curl.exe` are the only requirements.

| Source | Local path | Interpretation |
| --- | --- | --- |
| BDG2 building metadata | `raw/building_data_genome_2/metadata.csv` | International reference-building attributes |
| BDG2 electricity | `raw/building_data_genome_2/electricity_cleaned.csv` | Cleaned measured hourly readings, 2016–2017; not Barcelona meters |
| BDG2 weather | `raw/building_data_genome_2/weather.csv` | Weather corresponding to reference-building sites |
| Barcelona electricity 2025 | `raw/barcelona_electricity/2025_consum_electricitat_BCN.csv` | Aggregate consumption by date, postal code, sector and time band |
| Barcelona municipal PV 2025 | `raw/barcelona_municipal_pv/2025_municipal_photovoltaics.csv` | Installation inventory and publisher-reported indicators |
| Catalonia energy certificates | `raw/catalonia_energy_certificates/energy_certificates_catalonia.csv` | Full-Catalonia modeled certificate indicators; not measured electricity |
| Catalonia PV registry | `raw/catalonia_self_consumption/self_consumption_installations.csv` | Registered installations; not hourly generation |
| Catalonia demand | `raw/catalonia_hourly_demand/hourly_demand_catalonia.csv` | Regional demand; source uses daily rows with hourly columns |

`dataset_sources.json` lists original URLs and provenance. `logs/dataset_download_report.json`
records download status, resolved URLs, SHA-256, byte size, CSV row/column counts,
separator and encoding. Per-source logs and reports are retained. Validation at this
stage checks CSV structure, not units, missingness, timezone handling or model fitness.
`dataset_inventory.csv` provides a compact index of the eight core downloads.

## Additional reference files

`download_reference_data.py` caches publisher catalog metadata and the BDG2 README
and license under `metadata/`. It also downloads Barcelona municipality's official
cadastral buildings to `raw/cadastre_barcelona/barcelona_buildings.gml.zip`, retaining
the publisher's INSPIRE GML format. ZIP member CRCs are checked. Its report is
`logs/reference_download_report.json`. Attribute the Spanish Directorate General
for Cadastre when using its data; the official feed records the reuse terms.

## Sources requiring a later selection

Following the measured-data benchmark, the office simulation route also uses
`raw/simulation_weather/ESP_Barcelona.081810_IWEC.epw` and its companion design-day
file. These public reference-weather files were downloaded with the EnergyPlus
setup and are recorded in `reports/simulation_surrogate/setup_manifest.json`.
They are typical/reference climate data, not observed 2026 weather or a selected
roof's PVGIS output. Physical simulation results live in `synthetic/energyplus/`.

These are mentioned in the handoff but are not a defined bulk CSV download:

| Source | Status / input needed |
| --- | --- |
| PVGIS | A160 role-separated capacity/tilt/orientation inputs are in `inputs/roof_capacity/pvgis/`. Choose weather period/losses before hourly export; existing installed kWp remains unknown. |
| Barcelona solar map | Public polygons near A160 obtained through CARTO. Matching record dates to 2015; legacy comparison only. |
| ICGC LiDAR and imagery | A160 LAZ acquired 2022-06-01; finalized ortho 2025-06-18 and newest provisional image 2026-03-16 obtained under `raw/roof_capacity/A160/`. |
| DOE/NREL End-Use Load Profiles | Optional U.S. simulation reference; select release, building archetype and scenario before downloading a subset. No U.S. data is substituted for Barcelona ground truth. |
| REE/REData | Pending selected emissions-accounting year, system boundary and tariff assumptions; save dated exports in `manual_exports/emissions_tariffs/`. |
| ESIOS | Excluded by the handoff because authenticated API dependencies are out of scope. |
| Barcelona Energy Agency | Guidance/reference portal, not a specified machine-learning data file. |
| CEA/EnergyPlus | Optional simulation tools; outputs require a defined simulation and are not downloadable building measurements. |
| RID / WEATHER-5K | Historical/deprioritized sources in the handoff; outside the agreed core dataset set. |

No host or participant building is selected by these downloads. `inputs/` and
`synthetic/` are reserved for later case-study inputs and explicitly assumed schedules.
