# Roofscapes research dashboard

Local read-only integration of the approved seven-view architectural prototype.
No framework, build step, Node runtime, model loading or new runtime dependency.

## Launch and reload

From the workspace root:

```powershell
.\.venv\Scripts\python.exe -m ui.server
```

Open **http://127.0.0.1:8765**. Use `--port 8766` if necessary. Stop with Ctrl+C.
The service binds to loopback only; it does not publish a website. Data/assets
work offline; external evidence links need internet. Opening `index.html` directly
is unsupported and leaves metrics pending without the API.

Files are read on each request. Refresh to load reviewed repository updates;
no inference, training or rooftop regeneration runs. Export a scenario template
to retain controls and provenance before refreshing.

## Connected evidence and pending results

The UI reads the public candidate inventory, both A160 scenario CSVs/GeoJSONs,
reference coverage/IoU, capture dates and the municipal record's legacy status.
Office metrics, split counts and reference geometry come from model reports.
The hourly evaluation card counts actual validation + test rows, not invented
training hours. Scientific sources remain authoritative for all findings.

Existing installed kWp and actual generation remain null. Official hypothetical
PVGIS sensitivity is now available separately: see [the PV integration](docs/pv-integration/README.md).
Site/mixed-use demands, evaluated sharing and impacts remain pending.
The normalized rhythm explorer is `ILLUSTRATIVE_NOT_SIMULATED`, never hourly kWh.
Strategy controls define comparisons and execute no accounting computations.
The conceptual neighborhood artwork is separate from the real north-up roof
polygons (WGS84 source with a local metric display projection).

The JSON export is an unexecuted `UI_SCENARIO_TEMPLATE`, retaining assessment,
scenario, controls, source hashes/dates and model/commit metadata. Actual installed
kWp and unfinished energy/impact fields stay null. It is not a valid pipeline
execution config. Retrospective, incremental and existing generation roles stay
separate. Source modification UTC timestamps are not capture dates; UI timestamps
render in `Europe/Madrid`. Educational hour controls are civil-hour labels only.

## Files and API

- `data.py`: stdlib projection of fixed public CSV/JSON sources; no arbitrary paths.
- `server.py`: GET/HEAD API and static allowlist, loopback only; rejects writes.
- `index.html`, `styles.css`, `assets/neighbourhood.jpg`: approved shell, styles,
  extracted artwork. The supplied original HTML remains unchanged.
- `integration.css`, `app.js`: data states, controls, real roof map, source drawer,
  responsive navigation, focus/contrast improvements and export.
- `profiles.js`: educational arrays segregated from repository findings.
- `tests/`: optional baseline capture and offline browser acceptance.
- `integrations/`, `design-tools.json`: [persistent Stitch setup](integrations/README.md).
  Account metadata and credential helpers are not served by the dashboard.

See [API contract](API.md), [baseline](../docs/ui_integration_baseline.md),
[implementation report](docs/IMPLEMENTATION_REPORT.md), [review summary](docs/REVIEW.md)
and [browser results](docs/browser_results.json). The evidence drawer closes with
Escape and restores focus. Missing or corrupt sources remain pending.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Optional browser QA is isolated from modeling dependencies:

```powershell
.\.venv\Scripts\python.exe -m venv .venv-ui
.\.venv-ui\Scripts\python.exe -m pip install -r requirements-ui-test.txt
.\.venv-ui\Scripts\python.exe ui/tests/browser_smoke.py
```

Installed Google Chrome is required (`channel='chrome'`). Routine QA does not
download browsers or use an external account/API. The script starts an ephemeral
loopback server and stops it on exit. [Screenshots](docs/screenshots/) cover all
seven desktop/mobile views. `ui/docs/preservation.json` freezes model/report/
retrospective/template hashes; regression tests verify them without rewriting data.
Run `ui/tests/baseline.py` only to deliberately recapture the supplied original.

## Next gated work

1. Review the integrated existing-PV comparison and hypothetical PVGIS explorer.
   Stitch is authenticated and the approved HTML is linked to the private Research
   Studio project; graphic redesign remains separate from scientific development.
2. Obtain actual A160 PV specifications/installation records and roof-access
   details. Image area/row blocks are not verified installed kWp.
3. Refine explicit hypothetical PVGIS assumptions as needed, or establish a separate
   verified existing-system generation input after installation evidence arrives.
4. Prepare an A160-appropriate office simulation domain and separate school,
   residential and hotel archetypes before AI/domain expansion or demand display.
5. Freeze share plans, evaluate on independent aligned demands, preserve energy
   conservation/no-gain cases, then apply dated sourced impact assumptions.

Demand/sharing/impact packages remain prepared rather than executed. Existing
PVGIS/inference/accounting guards remain; the case-study boundary now additionally
rejects explicitly hypothetical/ineligible supply CSVs. No model was retrained.

Automatic acquisition: `python -m pipeline pvgis-acquire`. The UI reads cached
results; it never calls JRC from browser JavaScript. See
[acquisition/manual-fallback instructions](../pipeline/step_03_pvgis/README.md).
