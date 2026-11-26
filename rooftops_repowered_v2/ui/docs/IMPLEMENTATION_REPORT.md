# First UI integration milestone — 15 November 2026

**Follow-up:** priorities 1–2 now include existing-PV comparison and official
hourly PVGIS sensitivity. See [current PV integration](pv-integration/README.md)
for the 70-test / 11-general-browser / 5-PV-browser verification and new screens.
The original first-pass record below is retained as implementation history.

Branch: `feat/ui-integration-a160`. Base: `3cb20b9e58152829a87f82d1805ee323e314e79d`.
Exact local review commits: `git log main..feat/ui-integration-a160`. No merge,
push, deployment, model retraining or new scientific experiment was performed.

The approved seven-view prototype now reads actual A160/public/model evidence
through a small stdlib Python API. Original artwork/palette/layout/interactions
are retained. No frontend framework or production dependency was introduced.
Real roof GeoJSON and a keyboard-usable source drawer are added. Unknown
installed capacity and unavailable energy/impact outcomes remain null/pending;
normalized curves remain explicitly illustrative. Exports are unexecuted templates.

Connected sources: both scenario CSVs/GeoJSONs, reference metadata/IoU, roof
readiness, public candidates, office metric/readiness/domain/split manifests.
The model card shows error against simulated reference loads, not real A160
accuracy. Its hourly-count card sums validation + test rows in the source CSV.

| Check | Actual result |
| --- | --- |
| Baseline Python | 49 passed after permitting Windows pytest temp access |
| Final Python | **61 passed**, 0 failures, 3.20 s |
| Browser acceptance | **10 grouped checks passed**, no page errors; Chrome 157.0.8103.51 |
| Responsive views | All 7 screens at 1440×1000 and 390×844; no page overflow |
| Data/interactions | CSV-matching scenarios/model MAE, both maps, typology/hour, all strategies, evidence focus/Escape, desktop/mobile export |
| Pending/failure states | No substituted results; backend failure disables export and leaves values pending |
| API boundaries | Allowlisted reads, rejected writes/queries/paths/Host, no credential/private-path payloads |
| Preservation | Hashes match original model files, office reports, frozen roof prediction and original supplied HTML |
| Stitch unit tests | Config preservation/idempotency and no blind duplicate creation; no credentials required |

Commands: [UI README](../README.md). [Browser results](browser_results.json),
[preservation hashes](preservation.json), [all screenshots](screenshots/).
Examples: [desktop overview](screenshots/desktop-overview.png),
[roof](screenshots/desktop-roof.png), [demand](screenshots/desktop-demand.png),
[mobile overview](screenshots/mobile-overview.png), [mobile roof](screenshots/mobile-roof.png).
Final captures show the working implementation based on setup commit `2224f19`,
before the dashboard commit. They do not imply scientific reports were regenerated.

The Stitch endpoint is registered globally. Automatic OAuth failed with dynamic
registration unsupported. An encrypted Windows credential helper is configured
and a masked setup window opened. Authentication/new project remain pending
until the user enters a valid key and a live check succeeds. No project link or
connected-account claim is fabricated. See [Stitch setup](../integrations/README.md).

No scientific method, original metric, model, V1 source, roof prediction or historic
provenance record changed. Remaining needs: existing A160 PV specifications/access
plan, PVGIS settings/export, site-appropriate physics domains, independent sharing
evaluation and dated impact factors. The smallest next action is to authenticate
Stitch/review the UI; the smallest research decision is to obtain installation
evidence before selecting actual-system PVGIS assumptions.
