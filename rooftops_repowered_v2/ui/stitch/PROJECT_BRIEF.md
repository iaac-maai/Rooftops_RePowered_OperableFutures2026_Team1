# Roofscapes Research Studio — design handoff

Create/refine the research dashboard's **graphics** using the approved parchment,
forest-green navigation, muted PV blue, golden connection lines and conceptual
chamfered Poblenou artwork. Retain seven views: overview, roof intelligence,
solar production, demand prediction, energy sharing, impacts, sources/evidence.

The current implementation is `ui/index.html`, `styles.css`, `integration.css`,
`profiles.js`, `app.js`, and `assets/neighbourhood.jpg`. Review the fourteen
desktop/mobile captures in `ui/docs/screenshots/` and the untouched original
`UI Interface/Roofscapes_UI_Template_Editable_Package/index.html`.

Data come from a read-only API, not design constants. Retain IDs, controls and
bindings or provide an explicit mapping when refactoring. Existing installed A160
kWp is unknown. Retrospective potential and conditional additional PV are separate
concepts and are not existing generation. Educational curves must remain visibly
`ILLUSTRATIVE_NOT_SIMULATED`, normalized 0–1, never hourly kWh.

Keep pending states for real generation, A160/mixed-use demand, allocation results
and impacts. Preserve source dates, reference limitations, the legacy municipal-map
warning and the office model's restricted simulation domain. Do not redesign the
concept illustration into a purported surveyed map; actual roof GeoJSON is separate.

Do not change models, historic reports or scientific results while editing graphics.
After importing design changes, rerun Python API and browser acceptance tests.
The live Stitch project resource/link belongs in `ui/design-tools.json` only after
it is returned by the authenticated service.
