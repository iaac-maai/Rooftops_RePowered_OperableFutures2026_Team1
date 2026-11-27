# Step 09: Publish report

**Question this step answers:** how do we show the results so anyone can check them?

`export_site_data.py` collects the outputs of steps 03 to 09 and `docs/SOURCES.md` into one file, `website/data/site_data.json`, which the website in [`../../website/`](../../website/) reads. Every headline number in it carries a label: *measured* (real prices or meters), *modelled* (computed by the pipeline) or *assumption* (a value we chose), and where it comes from.

The website shows the **CEP9 Institut (Institut Quatre Cantons, Poblenou)**. To rebuild it, run from `pipeline\` (steps 01-03 need internet and the LiDAR sheets 433583 and 433584; the rest runs offline):

```
python -m step03_simulate_generation.shade_yield --lat 41.404361 --lon 2.2 --laz-dir data\lidar --usable data\roof\cep9_yellow_usable.geojson --panel cep9_540 --max-panels 108 --out data\pv\cep9_institut
python -m step03_simulate_generation.scale_panels --yield data\pv\cep9_institut_yield.json --hourly data\pv\cep9_institut_hourly.csv --panels 108 --out data\pv\cep9_institut_108
python -m step04_read_host_demand.host_table --solar data\pv\cep9_institut_108_hourly.csv --host-kind school --host-floor-m2 1811.7 --building-id cep9 --out data\host\cep9
python -m step06_prices_and_battery.battery_size --host-dir data\host\cep9 --compare-types --out data\battery\cep9
python -m step07_share_energy.candidates --host-dir data\host\cep9 --lat 41.404361 --lon 2.2 --candidates-csv examples\cep9_members.csv --max-distance 2000 --join-rate 1 --out data\neighbours\cep9
python -m step07_share_energy.battery_agent --host-dir data\host\cep9 --neighbours-dir data\neighbours\cep9 --prices-dir data\prices --out data\sharing\cep9
python -m step07_share_energy.agreed_shares --host-dir data\host\cep9 --neighbours-dir data\neighbours\cep9 --shares host=0.30,maria_espinalt=0.13,can_felipa=0.13,bombers_llevant=0.14,homes_30=0.30 --guest-price 0 --out data\agreed\cep9
python -m step08_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp 58.32 --out data\investment\cep9
python -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\neighbours\cep9 --sharing-dir data\sharing\cep9 --agreed-dir data\agreed\cep9 --prices-dir data\prices --kwp 58.32 --connection legal --out data\roi\cep9_legal
python -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\neighbours\cep9 --sharing-dir data\sharing\cep9 --agreed-dir data\agreed\cep9 --prices-dir data\prices --kwp 58.32 --connection wired --out data\roi\cep9_wired
python -m step09_publish_report.export_site_data --name cep9 --yield data\pv\cep9_institut_108_yield.json --roof-yield data\pv\cep9_institut_yield.json --label "CEP9, Institut Quatre Cantons roof, Poblenou" --host-label "Institut Quatre Cantons" --host-short "the Institut" --host-kind school --max-distance 2000 --lat 41.404361 --lon 2.2 --note "..." --reach-note "..." --host-use-note "..." --actual examples\cep9_actual.json
```

Why these values (all ASSUMPTIONS unless marked):
- **Only the Institut roof (yellow).** All 108 panels are on the Institut Quatre Cantons; the Escola Pere IV next door (red) is **not part of CEP9** [CEP9, email from César Ochoa, 27 Nov 2026]. The two-roof run is kept only as an extra case, "what if the school next door joined" (`data\pv\cep9_v2`, `data\host\cep9_both`).
- `--panel cep9_540 --max-panels 108`: the real panel and count [CEP9 tender]. Our layout rule (south-facing rows spaced for no shade at a 25° sun) fits only **85 panels** on that roof (577 m² usable, with the 4 look-alike rectangles as obstacles); the real plant is East-West "Delta Wing", back to back [CEP9, 27 Nov 2026]. `scale_panels` multiplies the 85-panel hourly output by 108/85 (**ASSUMPTION**: same yield per panel): **58.32 kWp, 77,404 kWh a year**, against about 73,750 reported [CEP9 presentation] (+5.0%). The later steps use `--kwp 58.32`. The roof section of the website still draws our 85 panels (`--roof-yield`). Before the rebuild, refresh the "Actual" blocks from the roof reading: `python -c "from step09_publish_report.update_roof import refresh_actual_blocks; refresh_actual_blocks('examples/cep9_actual.json', 'data/roof/cep9_yellow_existing_panels.geojson', 'yellow', roof_json='data/roof/cep9_yellow.json')"`.
- `--host-floor-m2 1811.7`: x 60 kWh/m2 = 108,700 kWh a year, the 2018 average of Barcelona's municipal institutes [Consums Energètics Edificis 2008-2018]. (Catastro's 3 floors x 1,422.5 m2 x 60 kWh/m2 would give 256,000.)
- `examples\cep9_members.csv`: the real CEP9 members [CEP9 presentation]; yearly use = 2018 average of that building type [Consums Energètics Edificis 2008-2018], homes by our step 05 rule; positions from step 01 (`step01_select_host/cases/cep9.json`), distances edge to edge from the Institut's outline (Can Felipa 10 m, fire station 83 m, Maria Espinalt 258 m); the 30 homes' location is private.
- `agreed_shares --shares`: CEP9's **real fixed split**: Institut (host) 0.30, Maria Espinalt 0.13, Can Felipa 0.13, fire station 0.14, 30 homes 0.30 [CEP9, 27 Nov 2026], power given for free (`--guest-price 0`). It replaces our earlier guess (host 0.30, homes 0.232, the rest equal). Step 08's `roi.py --agreed-dir` shows it as the reference row "CEP9 real terms".
- `--lat 41.404361 --lon 2.2`: the Institut's own point (step 01, `cases/cep9.json`). Until 27 Nov 2026 the commands used 41.40458605, 2.20067448, which is the Escola Pere IV point.
- `--max-distance 2000`: CEP9's own 2 km radius [CEP9 presentation; 2 km / 5 km now, CEP9, 27 Nov 2026], instead of the tool's 100 m.
- **Rebuilt on 27 Nov 2026** with the commands above, plus `python -m step06_prices_and_battery.price_model`, the no-fee legal run (`roi ... --manager-fee-eur-per-member 0 --out data\roi\cep9_legal_fee0`) and `optimise --mode legal --out data\match\cep9_legal`. The export took `--property data\host\cep9_yellow.json --property examples\a160_building.json`, the notes in the warnings banner, and then the roof section was redrawn on the Institut outline:
  `python -c "from step09_publish_report.update_roof import update_roof; update_roof('data/pv/cep9_institut_yield.json', 'examples/cep9_actual.json', chosen='max', label='CEP9, Institut Quatre Cantons roof', footprints='step01_select_host/cases/cep9_map.geojson', usable=['data/roof/cep9_yellow_usable.geojson'])"`
- **New section "25-year return" (step 08):** the owner's money over 25 years for A grid, B neighbours, C battery, B+C, and CEP9's real terms. It has a choice of how the guests are linked (legal with a €25 fee, legal with no fee, wired), a discount-rate slider (the page re-discounts the yearly cash that `roi.py` wrote, with the same formula), a table, the break-evens and the "what moves the answer" table. It reads the `roi` block of `site_data.json`.


It needs these folders from the earlier steps: `data\host\<name>` (04), `data\prices` (06), `data\battery\<name>` (06), `data\neighbours\<name>` (07), `data\sharing\<name>` (08), `data\investment\<name>` (09).

What the website shows: the roof and its monthly solar, spare solar for every hour of the year, the buildings within 100 m and their daily use, real hourly prices and the forecast test, the battery sizes and types with an example day run by the battery agent, and the owner's money with a **guest-discount slider** (default 10%, team decision 15 Nov 2026). How to view and publish it: [`website/README.md`](../../website/README.md).

Still to add: a 3D view (V1's ArcGIS map is in the V1 repository) and the real A160 case.
