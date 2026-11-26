# Public read-only API — schema 1.1

GET/HEAD, UTF-8 JSON, `Cache-Control: no-store`. Loopback only; no permissive CORS.
Writes return 405; unknown paths 404; invalid/duplicate query parameters 400.
Only the map and hypothetical-hourly endpoints accept allowlisted query parameters. No account credentials, arbitrary
files, private meters, raw caches or local absolute paths are served.

| Endpoint | Response |
| --- | --- |
| `/api/status` | Commit/version, generated/updated UTC stamps, display timezone, source-aware stages |
| `/api/dashboard` | Combined snapshot of the following public views |
| `/api/case-study/buildings` | Public candidates, uses, host/source and verification flags |
| `/api/roof/A160/scenarios` | Separate retrospective/additional groups, real CSV rows, hashes, units/assumptions; installed kWp null |
| `/api/roof/A160/map?assessment=…&scenario=…` | Real WGS84 footprint, eligible and panel GeoJSON; only `retrospective/additional` and `conservative/base/optimistic` accepted |
| `/api/roof/A160/reference` | Reference coverage/sensitivity, IoU, capture dates, limitations, legacy map comparison |
| `/api/roof/A160/existing-pv` | Existing-PV dossier, unknown installed specifications and observed-vs-predicted area/IoU comparison |
| `/api/pvgis/hypothetical/hourly?scenario=retrospective_base` | Exact cached modeled UTC samples, source/model metadata, hypothetical/ineligible flags; six fixed scenario IDs only |
| `/api/models/office-surrogate` | Reported metrics/splits/domain, model version, simulated origin and transfer restriction |
| `/api/pvgis/status` | Actual generation pending; separate hypothetical scenario summaries, assumptions, source hashes and acquisition modes |
| `/api/demand/status` | Pending site/mixed-use model domain and reference demand |
| `/api/sharing/status` | Pending aligned supply/load and independent evaluation |
| `/api/impact/status` | Pending balances and dated sourced assumptions |
| `/api/evidence` | Public URLs, relative evidence paths, dates, units and limitations |

Source states are `available`, `partial`, `pending`. Evidence labels distinguish
`AVAILABLE_REPOSITORY_RESULT`, `PROVISIONAL_ESTIMATE`,
`VALIDATED_SIMULATION_DOMAIN`, `UNVERIFIED_REAL_WORLD_TRANSFER`,
`MISSING_SOURCE_INPUT`, `ILLUSTRATIVE_NOT_SIMULATED`.

Unknown values are null. A genuine zero-module geometric scenario may be 0 kWp;
missing generation/load/savings never become zero findings. Missing/corrupt sources
stay pending. Counts are integral, numbers finite/nonnegative, and capacity must
equal count × assumed Wp. Duplicate/unknown scenarios are rejected.

Source keys/paths are compiled into `data.py`. Requests cannot supply paths.
Escaping paths/symlinks are rejected. GeoJSON properties are replaced by fixed
public layer/assessment/scenario properties. The retrospective map never includes
observed reference as a predictor feature; reference comparison is separate.

Provenance includes source SHA256, relative path and file-update UTC timestamp.
File updates are **not acquisition dates**; capture dates are separate fields.
Time metadata uses `timestamp_utc`, rendered in `Europe/Madrid` with Intl/DST.
Illustrative controls are civil-hour labels, not annual energy samples.

Future energy outputs need explicit provenance/role/calendar checks and reviewed
adapters. Existing pipeline validation gates remain authoritative.
