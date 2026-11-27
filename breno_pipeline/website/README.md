# Website

The results page for the tool: one page, one section per question, every number tagged *measured*, *modelled* or *assumption* with its source.

- `index.html`, `styles.css`, `app.js`: the page. Plain HTML, CSS and JavaScript, no build step. Charts are drawn as SVG by `app.js`.
- `data/site_data.json`: everything the page shows. **Don't edit it by hand.** It is written by the pipeline.

## Update the numbers

After running steps 03 to 09 for a case (see `pipeline/README.md`), from the `pipeline` folder:

The website shows the **CEP9 school (Institut Quatre Cantons, Poblenou)**. To rebuild it, run from `pipeline\` (steps 01-03 need internet and the LiDAR sheets 433583 and 433584; the rest runs offline):

```
python -m step03_simulate_generation.shade_yield --lat 41.404361 --lon 2.2 --laz-dir data\lidar --usable data\roof\cep9_yellow_usable.geojson --panel cep9_540 --max-panels 108 --out data\pv\cep9_institut
python -m step04_read_host_demand.host_table --solar data\pv\cep9_institut_hourly.csv --host-kind school --host-floor-m2 1811.7 --building-id cep9 --out data\host\cep9
python -m step06_prices_and_battery.battery_size --host-dir data\host\cep9 --compare-types --out data\battery\cep9
python -m step07_share_energy.candidates --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --candidates-csv examples\cep9_members.csv --max-distance 2000 --join-rate 1 --out data\neighbours\cep9
python -m step07_share_energy.battery_agent --host-dir data\host\cep9 --neighbours-dir data\neighbours\cep9 --prices-dir data\prices --out data\sharing\cep9
python -m step07_share_energy.agreed_shares --host-dir data\host\cep9 --neighbours-dir data\neighbours\cep9 --shares host=0.30,maria_espinalt=0.13,can_felipa=0.13,bombers_llevant=0.14,homes_30=0.30 --guest-price 0 --out data\agreed\cep9
python -m step08_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp 52.38 --out data\investment\cep9
python -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\neighbours\cep9 --sharing-dir data\sharing\cep9 --agreed-dir data\agreed\cep9 --prices-dir data\prices --kwp 52.38 --connection legal --out data\roi\cep9_legal
python -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\neighbours\cep9 --sharing-dir data\sharing\cep9 --agreed-dir data\agreed\cep9 --prices-dir data\prices --kwp 52.38 --connection wired --out data\roi\cep9_wired
python -m step09_publish_report.export_site_data --name cep9 --yield data\pv\cep9_institut_yield.json --label "CEP9 school roof, Poblenou" --host-label "Institut Quatre Cantons" --host-kind school --max-distance 2000 --lat 41.40458605 --lon 2.20067448 --note "..." --reach-note "..." --host-use-note "..." --actual examples\cep9_actual.json
```

Why these values (all ASSUMPTIONS unless marked):
- **Only the Institut roof (yellow).** All 108 panels are on the Institut Quatre Cantons; the Escola Pere IV next door (red) is **not part of CEP9** [CEP9, email from César Ochoa, 27 Nov 2026]. The two-roof run is kept only as an extra case, "what if the school next door joined" (`data\pv\cep9_v2`, `data\host\cep9_both`).
- `--panel cep9_540 --max-panels 108`: the real panel and count [CEP9 tender]. Our layout rule (rows spaced for no shade at a 25° sun) fits only **97 panels, 52.38 kWp, 69,508 kWh a year** on that roof, against the real 108 panels, 58.32 kWp and about 73,750 kWh [CEP9 presentation]. So the later steps use `--kwp 52.38`, to keep cost and output consistent. Per kWp our model gives 1,327 kWh against the real 1,265 (+5%).
- `--host-floor-m2 1811.7`: x 60 kWh/m2 = 108,700 kWh a year, the 2018 average of Barcelona's municipal institutes [Consums Energètics Edificis 2008-2018]. (Catastro's 3 floors x 1,422.5 m2 x 60 kWh/m2 would give 256,000.)
- `examples\cep9_members.csv`: the real CEP9 members [CEP9 presentation]; yearly use = 2018 average of that building type [Consums Energètics Edificis 2008-2018], homes by our step 05 rule; three positions not checked (listed at the host).
- `agreed_shares --shares`: CEP9's **real fixed split**: Institut (host) 0.30, Maria Espinalt 0.13, Can Felipa 0.13, fire station 0.14, 30 homes 0.30 [CEP9, 27 Nov 2026], power given for free (`--guest-price 0`). It replaces our earlier guess (host 0.30, homes 0.232, the rest equal). Step 08's `roi.py --agreed-dir` shows it as the reference row "CEP9 real terms".
- `--max-distance 2000`: CEP9's own 2 km radius [CEP9 presentation; 2 km / 5 km now, CEP9, 27 Nov 2026], instead of the tool's 100 m.
- **Not done yet:** `website/data/site_data.json` was not regenerated after this correction, so the page still shows the old two-roof "Actual" tab, and `app.js` still says "the two roofs". Rerun the block above (it also needs `price_model` from step 06) and update that sentence in `app.js`.


`--name` is the folder name you used in `data\host\<name>`, `data\sharing\<name>` and so on. `--lat --lon` are the host's position (the same as in step 07). Then commit `website/data/site_data.json` and push.

## See it on your laptop

```
cd website
python -m http.server 8000
```

Open http://localhost:8000. (Opening `index.html` by double-click doesn't work, because the browser won't load the data file that way.)

## Online

This folder now lives in the group repo at `breno_pipeline/website/`. GitHub only runs workflows from the repo's top-level `.github/` folder, so `breno_pipeline/.github/workflows/pages.yml` does **not** run here; it is kept for reference. To put this page online, the team first has to choose what the group repo's single GitHub Pages site shows (this page, the team's `website/`, or both under one address), then copy the workflow to `.github/workflows/` at the top of the group repo with `path: breno_pipeline/website`. Until then, view it locally as above.

## What the page does itself

Only the guest-discount slider does any maths, using the same formula as step 08 (`owner_total_at_discount`): owner = host savings + (1 − discount) × guests' solar at grid price + export. Everything else is read from the data file.
