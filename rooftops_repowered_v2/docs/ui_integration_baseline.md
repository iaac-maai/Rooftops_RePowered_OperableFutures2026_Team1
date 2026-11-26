# UI integration baseline — 15 November 2026

Base SHA: `3cb20b9e58152829a87f82d1805ee323e314e79d` (`main`, `test 1`).
Feature branch: `feat/ui-integration-a160`. `git fetch origin` succeeded; local
HEAD and `origin/main` matched before development. No merge, push or deployment
was requested or performed.

The configured remote is
`https://github.com/SindhujaDavuluri-IAAC/researchstudio2026_rooftops_repowered.git`.
The handover names a different owner/repository. The actual remote is preserved;
no remote configuration was changed and no unverified repository was pulled.

The working tree had three untracked user additions: the UI handover, launch
prompt and `UI Interface/`. Existing tracked files were clean. The approved
prototype is `UI Interface/Roofscapes_UI_Template_Editable_Package/index.html`;
it remains unchanged. Its original stylesheet and artwork are reused in `ui/`.

Baseline commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pipeline status
.\.venv-ui\Scripts\python.exe ui/tests/baseline.py
```

The first restricted test invocation returned 45 passed / 4 setup errors because
pytest could not access its Windows temporary directory. With that access allowed,
the unchanged suite passed **49 tests** in 2.43 s. This was an execution-permission
issue; pipeline code was not modified to make the baseline pass.

All seven original desktop views were opened in installed Chrome and captured
before integration, with a mobile overview. [Baseline results](../ui/docs/baseline/results.json)
record browser version and no mobile horizontal overflow. Examples:
[desktop overview](../ui/docs/baseline/desktop-overview.png),
[desktop roof](../ui/docs/baseline/desktop-roof.png),
[mobile overview](../ui/docs/baseline/mobile-overview.png).

[Preservation hashes](../ui/docs/preservation.json) cover model artifacts/metadata,
the office-surrogate reports, the frozen retrospective prediction and the approved
source HTML. No model, V1 file, historic metric or rooftop prediction is regenerated.

Available sources: both A160 scenario CSVs and GeoJSONs, image-reference metadata
and validation, roof-readiness report, public candidate inventory, office model
metrics/readiness/domain/split manifests. Existing A160 installed kWp remains
unknown; the existing office model is not an A160 or mixed-use demand model.
PVGIS site generation, site-appropriate demands, evaluated allocation outputs and
sourced impacts remain pending. Unfilled source inputs are not filled with zeros.
