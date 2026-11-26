# Priorities 1–2: existing-PV comparison and PVGIS integration

Implemented 15 November 2026. The local tool remains available at
**http://127.0.0.1:8765**. Refresh the browser to load the latest interface.

## Existing PV and our assessment

The Solar production view now shows an existing-PV evidence dossier. The actual
installed capacity, module count/Wp, tilt/orientation and inverter details remain
unknown, as explicitly clarified by the user. The observed image coverage is
410.72 m², not installed kWp. Its threshold-sensitivity range is not a statistical
confidence interval or a module count.

Roof intelligence now compares that image reference with all three hypothetical
layouts using projected area, area difference and spatial IoU. For example,
base predicted coverage is 517.07 m² and IoU about 0.265. The interface explains
post-installation LiDAR contamination and distinguishes installation agreement
from maximum-capacity verification. No installed-capacity error is fabricated.
The cached municipal comparison remains a 2015 historical benchmark only.

## Official modeled generation

The new automatic CLI acquired four unique official PVGIS responses, normalized
into five positive-capacity scenario outputs of 8,760 hourly records each.
The two 1.26 kWp additional cases share an exact cached API response. The zero
case skips simulation. No manual PVGIS or municipal-map download was needed.

| Hypothetical case | Capacity assumption | Modeled annual energy, 2017 |
| --- | ---: | ---: |
| Retrospective conservative | 95.34 kWp | 133,390.53 kWh |
| Retrospective base | 110.88 kWp | 155,132.60 kWh |
| Retrospective optimistic | 116.76 kWp | 163,359.33 kWh |
| Conditional additional base/optimistic | 1.26 kWp each (alternative cases) | 1,762.87 kWh each |

These are **hypothetical physics-model outputs**, not actual A160 plant
generation. Alternative scenarios are never summed. Assumptions are explicit:
PVGIS 5.3/SARAH3 year 2017, 14% generic losses, crystalline silicon, ventilated
free-standing mounting, layout-derived tilt/aspect and terrain horizon only.
Actual installed specifications are still unknown. Local roof shading/inverters
are unverified, and this weather differs from the existing office IWEC simulation.

The explorer selects scenario and local date, plots actual acquired samples,
shows modeled annual energy/source metadata and exports settings/provenance.
UTC timestamps and minute offsets are retained. Europe/Madrid DST and local
year-boundary days display their exact source-interval counts, without filling.

See [acquisition/import documentation](../../../pipeline/step_03_pvgis/README.md)
and the [run manifest](../../../reports/pvgis/A160/hypothetical_acquisition.json).
Raw responses, settings and normalized CSVs are saved separately under PVGIS
`hypothetical/` folders. Actual verified generation remains null. Existing importer
guards remain, and the sharing command also rejects explicitly ineligible/hypothetical
CSV inputs. No case-study balance is computed from these sensitivity outputs.

## Verification and previews

- **70 Python tests passed**: existing regressions/preservation, API/cache/temporal
  acquisition, HTTP failure/manual fallback, stale-source handling and supply gates.
- **11 general browser groups passed** across seven desktop/mobile views.
- **5 PV-workflow browser groups passed**, including comparison controls, source
  curves, 23/25-hour DST days, partial local year boundaries, zero-case skip,
  export metadata and mobile layout. No page errors.

[PV results](pv_workflow_results.json), [general UI results](browser_results.json),
[solar desktop](desktop-solar.png), [comparison desktop](desktop-comparison.png),
[solar mobile](mobile-solar.png), [all-view captures](all-views/).

No model artifact, frozen roof prediction or validated demand result changed.
New work is limited to read-only evidence/UI integration, acquisition/normalization
and stronger rejection of explicit hypothetical supply at the case-study boundary.

Stitch is authenticated, the private Research Studio project exists, and the exact
approved original HTML reference was uploaded and verified. Graphic redesign is
deferred. Demand-domain adaptation, independent sharing comparisons and sourced
impacts remain the subsequent work packages; this release does not claim they ran.
