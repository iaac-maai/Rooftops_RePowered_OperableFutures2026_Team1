# Barcelona sector-derived synthetic shapes

Generated from Daria's `energy_clean23-25.csv`, SHA-256 in `provenance.json`, using `scripts/barcelona_synthetic_reference.py`. Run from the workspace root:

```powershell
.\.venv\Scripts\python.exe scripts/barcelona_synthetic_reference.py 'C:\Users\Sindhuja Davuluri\Downloads\energy_clean23-25.csv'
```

The input has daily postal-code/economic-sector totals in four six-hour bands and an additional `No consta` category. This initial reference assumes postcode 08018 and uses complete 2023; 2025 ends in November. The generator excludes unallocated `No consta` values and records their totals. It splits each reported band evenly into six nominal hours and normalizes each sector to a unit annual sum. The resulting 8,760 rows per sector are **synthetic normalized shapes**, not hourly measurements, kWh or building demand. Units and original calendar/DST semantics of this supplied file require source verification. No weather alignment is implied.

Residential is only a broad reference for the homes; services combines many activities and cannot identify office, school or hotel patterns separately. Do not assign sector totals to buildings, infer conditioned floor areas or annual building consumption, train or validate an AI model on these curves, or use them as eligible energy-sharing inputs. An eventual building-level scenario requires independently sourced annual magnitudes, justified sector/typology mapping, hourly shape sensitivities, time and weather contracts, and validation. Compare alternative within-band shapes; flat hours are a transparent placeholder, not a finding.
