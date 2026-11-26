# Connect approved A160 dashboard to read-only repository evidence

The subsequent priority-2 change adds an unknown-specifications existing-PV
dossier, image-vs-prediction comparison, official PVGIS acquisition/manual fallback
and a separate hypothetical-generation explorer. Current verification is 70
Python tests plus 11 general and 5 PV browser groups; see [PV results](pv-integration/README.md).
Actual generation is still null and hypothetical supply is rejected by `match`.

The prototype had copied numeric literals and no backend. This change reads actual
roof scenarios, candidates, reference/source metadata and model reports through an
allowlisted local API. Seven views remain, with real roof geometry and an evidence
drawer. Unavailable energy/impact stages remain pending with null exports.

The loopback service rejects arbitrary reads/writes; credentials, raw caches,
private data and trained binaries are not served. Models, validation gates,
historic results and the original template are unchanged. Optional Stitch setup
registers the official endpoint with an encrypted Windows helper; the user's
authentication is still needed for project creation.

Validation: 61 Python tests; 10 offline browser acceptance groups; all desktop/
mobile views, controls, provenance, null/failure states and preservation checks.
See the implementation report/screenshots for evidence and limitations.

```powershell
git diff --stat main..feat/ui-integration-a160
git diff main..feat/ui-integration-a160 -- ui/data.py ui/server.py ui/app.js tests/test_ui_api.py
```

The branch/commits are local. No PR was pushed or automatically merged.
