# Step 03 — official PVGIS hourly acquisition

The actual A160 installation's capacity, count/Wp, tilt and orientation remain
unknown in `config/a160_existing_pv.json`. This step can acquire **hypothetical
capacity sensitivity** without promoting it to verified existing generation.

## Automatic acquisition

```powershell
.\.venv\Scripts\python.exe -m pipeline pvgis-acquire
```

Configuration: `config/pvgis_hypothetical.json`. It uses the documented official
[JRC seriescalc API](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en)
at `/api/v5_3/seriescalc`. Requests run server-side in Python, not browser AJAX.

Scenario capacities and hypothetical panel angles come from the frozen rooftop
CSV outputs. The three retrospective cases are counterfactual roof potential;
the positive additional cases are conditional new supply, separate from existing
PV. Zero capacity skips acquisition; duplicate parameters reuse one exact response.

Explicit current assumptions: SARAH3 historical year 2017, 14% system losses,
crystalline silicon and free-standing ventilated mounting. The [JRC manual](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en)
documents the generic loss default and mounting meanings. These are **sensitivity
assumptions**, not actual A160 module/inverter specifications. Layout-derived 10°
tilt and south-zero aspect around −44.11° are also hypothetical. Terrain horizon
is included; local roof/building/tree shadows and actual inverter effects are not
verified. The selected 2017 radiation is not the office model's IWEC weather.

## Files and provenance

- `datasets/raw/pvgis/A160/hypothetical/<request-hash>/`: exact response bytes,
  CSV, request parameters, HTTP metadata, retrieval UTC and source SHA256.
- `datasets/processed/pvgis/A160/hypothetical/<scenario>.csv`: normalized hourly
  energy, scenario/role/model fields, `hypothetical=true`, sharing eligibility false.
- Matching `.settings.json`: complete settings, assumptions, source/output hashes,
  timestamps, units and hourly/monthly/annual summaries.
- `reports/pvgis/A160/hypothetical_acquisition.json`: run/status manifest, failure
  details/manual fallback and actual installed capacity/generation remaining null.

Raw caches and normalized hourly CSVs remain local, like other large derived
datasets. Source/configuration, compact manifests/settings and summary evidence
are trackable. Regenerate the hourly cache with the acquisition command after a
fresh checkout; the UI shows pending sources until actual files are available.

The existing `import_hourly` and `require_hourly_index` perform P(W)/1000 conversion
for the one-hour energy approximation and reject missing/duplicate hourly steps.
The acquisition wrapper also checks chronological order, source year and complete
8,760/8,784-row coverage. **Original UTC minute offsets are preserved.** Nothing
is floored, reindexed, relabeled to another year or silently joined to demand.
Local display uses Europe/Madrid, including 23/25-hour DST days and partial local
dates at UTC-year boundaries. Annual summaries use the source UTC year.

The output is `SIMULATED_PHYSICS`, never observed meter generation. Cached source
hashes are checked before reuse. UI summaries/series become pending if acquisition
settings, rooftop sources or normalized output hashes change.

## Failure and manual CSV fallback

An HTTP/network/schema/temporal failure is recorded with no invented energy. If
automatic access fails, export an actual hourly PVGIS CSV for the exact declared
scenario/settings, then run:

```powershell
.\.venv\Scripts\python.exe -m pipeline pvgis-import-hypothetical --scenario retrospective_base --input YOUR_PVGIS_EXPORT.csv
```

All six IDs follow `retrospective|additional` + `_conservative|base|optimistic`.
Manual source bytes/hashes and the acquisition mode are preserved; its settings
are user-declared, not server-verified. Year/completeness/time/unit checks still
apply. A manual import remains hypothetical and sharing-ineligible.

## Existing generation and sharing gates

Neither command writes `datasets/processed/pv_hourly.csv`, the actual case-study
supply path. Existing `import-pvgis` settings/role checks remain intact.
`match` additionally rejects explicitly hypothetical/ineligible PV CSVs even if
someone manually repoints a configuration to one. No existing model or accounting
algorithm was retrained or replaced. Future actual-system generation needs
verified installation evidence and a separate eligible metadata/import path.

UI: `python -m ui.server`; see Roof intelligence's existing-vs-predicted comparison
and Solar production's clearly tagged hypothetical PVGIS explorer.
