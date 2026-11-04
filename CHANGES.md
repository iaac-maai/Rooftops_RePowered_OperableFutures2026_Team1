# Clean-up, 2 November 2026 (for Breno and Sindhuja)

Based on the repo after Breno's merge of PR #6 (`dbaf9bd`), with all of PR #6 included (step 5, the roof test set, lower roofs and exclusions, check_months, the new outputs). Nothing was lost: every deleted folder was an older or identical copy. You can delete this file once you've read it.

## What moved where

| Before | Now |
|---|---|
| `step1_find_building/step1_find_building/` (steps 1–4, tests) | `pipeline/` |
| `step2_read_the_roof/` (older copy of step 2) | deleted |
| `link_roofscapes/` (copy of the site without `config.js`, and of 3 step 2 files) | deleted |
| `roofscapes-repowered/` | `website/` |
| `roofscapes-repowered/roofs/` | `website/data/roofs/` |
| `README.md`, `README_step2.md`, `README_step4.md`, `README_step5.md` (inside the double folder) | `pipeline/step1/README.md`, `pipeline/step2/README.md`, `pipeline/step4/README.md`, `pipeline/step5/README.md` |
| `README_step1.md`, `README_step2.md` at the top | deleted (older copies) |
| `requirements.txt` + `requirements-step2.txt` | `pipeline/requirements.txt` (everything except the AI) + `pipeline/requirements-ai.txt` (PyTorch) |
| `step2/export_web.py` | `pipeline/web/export.py` (`python -m web.export lluria56`) |
| `tests/test_step2_web.py` | `pipeline/tests/test_web.py` |
| example outputs (`lluria56*`, `travessera308*`, `building.*`, `arago284t*`, `arago308*`, `bruc59*`, `diputacio311*`) | `pipeline/examples/` |
| `step1/__pycache__/` | deleted (now ignored by git) |
| `.gitignore` (inside the double folder, lines twice) | one `.gitignore` at the top. Outputs written in `pipeline/` are ignored now, so put results to share in `examples/`. `data/roof_exclusions.csv` is the one file in `data/` that git shares. |

Run commands from `pipeline/` now, instead of from the double folder.

## What's new

- **`--web` on step 4** (`step4.shade_yield` and `step4.batch`): sends the roof, every panel with its kWh and shade loss, the totals and the monthly kWh to the map. The map now **shows step 4's numbers** for those roofs ("Our pipeline") and keeps its own calculation only as a labelled "Quick estimate" for roofs not run yet. `--web` with no folder means `../website`.
- **`python -m web.buildings`**: downloads the study area's buildings from the city once → `website/data/buildings.json`. The map then stops asking the city server on every click inside the study area. (The roof list itself is Breno's `step4.roof_test_set`.)
- `step2.dataset` uses `lat,lon` when a row has them, like `step4.batch`, so it reads the roof test set directly.
- The map shows step 2's notes: a roof on the exclusion list ("Left out by hand: …") and lower roofs not counted.
- `step4.shade_yield` also writes `<out>_usable.geojson` when it reads the roof itself, and saves step 2's numbers in `<out>_yield.json`.
- Website: medium quality and live shadows off at start (turn them on in "Sun and shadows"), opens directly over the 9 blocks, "Hours of shadow" only runs while open, month-by-month bars, slider starts at 60% (same as step 4's 40% shade limit).
- New tests: `tests/test_web.py` (energy export), `tests/test_buildings.py`, and one in `tests/test_step4.py` (`--web`).

## The website's four screens (same day, later)

From Daria's design: a top bar with four tabs, all on the city's real 3D model.

- **Area**: roofs run by the pipeline coloured by kWh per m² of roof (colour steps in `website/config.js`), block numbers 1–9, the share of the blocks' own use their roofs cover (from step 5), panels, energy, homes, block by block, best roofs.
- **Building**: the Roof Report, plus a typical day for the month in the time bar and step 5's use and coverage for that building.
- **Sharing**: step 5's groups drawn on the map with arcs, with and without sharing, a card per group, the 500 m / 2 km / 5 km rule.
- **How it works**: the problem and the five steps, with images from `examples/`.
- **Time bar**: month and hour move the real sun on the map (and the typical-day chart); a Shadows switch.
- New for the pipeline: `step4.batch --web` sends each roof's block; roof files get `typical_day_kwh` (12 months × 24 hours, local time); `python -m web.sharing` sends step 5 to the map. New tests: `tests/test_sharing_web.py`, two more in `tests/test_web.py`.

## To do: put the tested roofs on the map

The outputs of Bruc 59, Diputació 311 and Aragó 284/308 in `examples/` were made before the lower-roof and exclusion rules (Aragó 284 looks like the sports court in the exclusion test, with 941 m² "usable" in its old reading). Rather than putting old numbers on the map, rerun them with `--web`, e.g. `python -m step4.batch data\roof_test_set\roof_test_set.csv --laz-dir data\lidar --out data\yield_all --block 5 --web`.

## Please check

The Python tests couldn't run where this was made (no geometry packages there). Run them once:

```
cd pipeline
pip install -r requirements.txt
python -m pytest tests
```

## The Groups map (3 November 2026)

The site now answers one question for the city: where to put solar panels. Two tabs instead of four:

- **Groups**: every group of buildings in its own colour (the roof with panels strong, the buildings that share it light, the rest pale). Click a group: everything else turns grey, and inside the group each roof shows how good it is for panels (best 20% to worst 20%), with the roof with panels outlined and our pipeline's panels on it. The panel lists the groups, and for one group: panels, kWh, cost, payback, how much of the members' use it covers, who joins and their share.
- The groups are Breno's step 5c (`data/communities.json`). Until that file is in, the browser makes a **preview** with the same rules (`COMMUNITY` in `website/config.js`), clearly labelled.
- **How it works** stays; step 5 is now "Groups".
- Removed: Area, Building (Roof Report) and Sharing tabs; `pipeline/web/sharing.py` and `tests/test_sharing_web.py`.
- New for the pipeline: `python -m web.communities` (step 5c → `website/data/communities.json`), test `tests/test_communities_web.py`.

## MATCHSOL (3 November 2026, later)

The question changed from "where to put panels" (on every roof that can take them) to "who shares power with whom".

- **Matches**: buildings coloured by what they are (homes with panels, homes whose roof is too shaded for panels, schools, offices), with power lines that change direction with the day and hour in the time bar. Click a match: the rest turns grey, and the panel shows its day, its members, who gives and who gets now, and what it shares a year.
- **Hourly split**: the share of a roof's power for each member and each hour, and the year file (8,760 hours) for the electricity company.
- **Money**: who pays whom, with a price slider; how the bill works.
- **How it works**: the idea, the law (5 km, a share for every hour), the success measure, the four steps.
- New `website/match.js`: the matching engine (typical days, step 5's use patterns, the pipeline's sun, growing matches by complementary schedules). It runs in the browser as a preview.
- Removed: the Groups tab, `pipeline/web/communities.py` and its test (step 5c itself stays in the pipeline).
