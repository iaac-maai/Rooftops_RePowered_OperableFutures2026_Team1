# V2 transfer to sindhu-pipeline

Snapshot of the V2 workspace transferred 26 November 2026. The V2 files are contained in this folder so the existing V1 repository is preserved. Includes datasets present locally under 100 MiB and trained `.joblib` files. Dataset sources and retrieval information are documented in `datasets/dataset_sources.json`, `datasets/README.md`, and the related reports. Local environments, software installations, transient caches and credentials are excluded.

At the user's instruction the following larger original datasets are not included; recover them from the source inventory and verify checksums:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `datasets/raw/building_data_genome_2/electricity_cleaned.csv` | 174977911 | `b6ffc9b4dfcefe5c753594730a08ae822b0d50fec6815abb8f185591e6c630a3` |
| `datasets/raw/catalonia_energy_certificates/energy_certificates_catalonia.csv` | 755162093 | `4de49583de748dd513efc26f2f5063323b6816d7d363299c002a7ff4dd952e17` |
| `datasets/raw/roof_capacity/A160/lidar/lidar-territorial-full1km432583.laz` | 303095100 | `389e62922f9daa3987e43f5ae59ce4a8df968d5d5b72ba9525290690c57b4adb` |

The separate Breno reference clone is not embedded by Git archive. Its repository URL, commit and scope are documented in `external/README.md`; obtain it independently. Respect source licenses and review data provenance before redistribution or scientific use. Hypothetical PV and synthetic demand remain ineligible as verified case-study inputs.
