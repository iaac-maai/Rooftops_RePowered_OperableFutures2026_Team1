# MATCHSOL — the 3D map

> Homes are empty at noon. Schools are empty on weekends. MATCHSOL matches them, so every solar kilowatt-hour is used in the neighbourhood.

The site shows the **Ajuntament de Barcelona 3D model** with four tabs in the top bar:

| Tab | What it shows |
|---|---|
| **Matches** | Every building of the 9 blocks, coloured by what it is: homes with solar panels, homes whose roof is too shaded or small for panels, schools, offices, and buildings in no match. **Power lines** (arcs with arrows) show who sends power to whom at the day and hour chosen in the time bar: on a weekday at noon from home roofs to schools and offices, at the weekend and in the summer holidays from school and office roofs to the homes, at night nothing. The panel: how much of the neighbourhood's solar power is used each building alone vs. matched, and the list of matches. **Click a match** (on the map or in the list): every other building turns grey; the panel shows a chart of its day (sun, homes' use, school and office use), who is in it, who gives and who gets at this hour, and what it shares and keeps a year. |
| **Hourly split** | For one roof of a match: the share of its power for every member and every hour (weekday, weekend, summer holidays), and a **year file** to download: one share per member for each of the 8,760 hours, adding up to 1, as the electricity company needs it. |
| **Money** | Who pays whom. A slider sets the price of a shared kWh, between what the grid pays for extra power (0.05 €) and what it charges (0.16 €), and shows what the buildings that give earn and what the buildings that get save, per building. How the bill works, and the two ways to pay (per kWh, or investing together). |
| **How it works** | The idea, the law (5 km, a share for every hour), how success is measured, and the four steps. |

**Find its match** (top bar): type an address in the 9 blocks; the map opens the match that building belongs to.

No account, no API key, no credit card.

## How the matching works (`match.js`)

1. **Every building, hour by hour.** For 24 typical days (12 months × weekday and weekend), each building gets its solar power and its use, hour by hour. It first uses its own roof's power; what is left is its **surplus**, what is missing its **need**.
2. **Grow the matches.** Start with the schools and offices (biggest first), then the home buildings with the most surplus. Each match keeps adding the building that lets it use the most extra solar power in a year: the one whose need falls when the others have surplus, or the other way round. Nearer buildings are preferred (the law allows 5 km; a match should stay a neighbourhood). A building joins only if it adds at least 200 kWh a year; at most 10 buildings per match (`config.js`, `MATCH`).
3. **Inside a match**, every hour the pooled surplus goes to the pooled need, in proportion. That gives the power lines, the hourly split table and the money.

**Success** = the share of the solar power used in the neighbourhood: each building alone, and matched.

## Where the numbers come from

This is a **preview, computed in your browser** (the page says so):

| What | Now (preview) | Next |
|---|---|---|
| What each building is (homes, school, office; flats, floor area) | the city's 3D model (`data/buildings.json`): use, floors, footprint | Catastro (our step 1 already reads it) |
| Each building's use, hour by hour | step 5's patterns (`config.js`, `USE`, same as `pipeline/step5/demand.py`) | Open Data BCN's meter data by postal code, user type and time of day (`python -m step5.bcn_data`) |
| Solar power, hour by hour | our pipeline (steps 2–4) for the roofs in `data/roofs/`, with their own typical days; the quick estimate (`solar.js`) for the others, scaled to match the pipeline, with the pipeline roofs' average sun shape | every roof run by the pipeline (`python -m web.export --all`) |
| Prices, CO₂ | `config.js`: 0.16 € per kWh bought, 0.05 € per kWh sold (step 5c), CO₂ 0.10 kg per kWh (ASSUMPTION, check with Red Eléctrica) | sourced values |

About CO₂: the panels avoid the same CO₂ whether their power is used next door or sold to the grid. What matching changes is **who gets the money**: the 0.11 € between the two prices stays in the neighbourhood instead of going to the grid.

## Run it

Open with a local web server (not by double-clicking):

- **VS Code:** right-click `index.html` → **Open with Live Server**, or
- **Terminal in this folder:** `python -m http.server 8000` → open http://localhost:8000

## Fill it with data (from the `pipeline` folder)

```
python -m web.buildings                                   # once: the study area's buildings (fast start)
python -m step4.roof_test_set --out data\roof_test_set    # once: every roof of the 9 blocks
python -m step4.batch data\roof_test_set\roof_test_set.csv --laz-dir data\lidar --out data\yield_all --web
```

Already ran step 4 without `--web`? `python -m web.export --all data\yield_all` sends the whole folder. Then reload the page: those roofs use the exact numbers.

## Keeping it fast

- **The heavy work happens once, in Python**, not in every visitor's browser. The matching is the exception for now: it takes well under a second for the 9 blocks.
- **One small file per roof** in `data/roofs/`. `index.json` stays small.
- **Our study area in one file** (`data/buildings.json`): the page does not wait for the city server.
- The page starts at medium quality with shadows off, and **Hours of shadow** only runs while its box is open.

Still slow on your laptop? In `config.js`, put the "simple volumes" 3D model first in `SCENE_LAYERS`.

## Files

| File | What it does |
|---|---|
| `index.html` | Page structure: top bar, the four tabs, the panel, the pages, time bar |
| `style.css` | Look of the page (colours and fonts at the top) |
| `config.js` | Service addresses, data files, the matching rules (`MATCH`), use patterns (`USE`), prices, colours, and **all assumptions** of the quick estimate |
| `solar.js` | Quick roof estimate: sun path, shade rays, sky view |
| `match.js` | The matching engine: typical days, use and sun shapes, growing the matches, the hourly split, the year file |
| `app.js` | 3D map, reading our data files, the buildings, the power lines, the four tabs, time bar |
| `data/buildings.json` | Our study area's buildings (`python -m web.buildings`) |
| `data/roofs/` | One file per roof run by the pipeline, and `index.json` |
| `img/` | Pictures for How it works (from `pipeline/examples`) |

## Data and tools

| Part | Source |
|---|---|
| 3D model on the map | Ajuntament de Barcelona, `Hosted/BCN_3DtoFeat/SceneServer` (falls back to `Hosted/3D_MTM`), geo.bcn.cat |
| Building footprints, height, roof form, use, cadastral ref. | Ajuntament de Barcelona, `Hosted/BCN_3DtoFeat/FeatureServer/22` (`multipatchOption=xyFootprint`) |
| Background map | Ajuntament de Barcelona vector map (falls back to OpenStreetMap) |
| 3D engine | ArcGIS Maps SDK for JavaScript 4.31, free with these public layers |
| Pipeline results | our Python code, `../pipeline` |
| The law | Real Decreto 244/2019 (shared self-consumption), Orden TED/1247/2021 (a share for every hour), Real Decreto-ley 7/2026 (up to 5 km) |

## Known limits (next steps)

- Ground-floor shops are not counted yet (they use power by day too), and buildings with other uses (shops, industry, parking) are left out of the matching.
- The preview counts flats from the city model (floor area ÷ 100 m²); Catastro has the real numbers.
- Every building of one kind follows the same day pattern; real meter data will make them differ.
- The split shares come from typical days. The real table is fixed in advance and can change every four months, so a building that uses less than planned sends its unused share to the grid.
- The map covers the buildings within 350 m of the centre of the 9 blocks. Without `data/buildings.json` it loads them from the city server once per visit (slower).
- Values marked ASSUMPTION in `config.js` need sources (PVGIS, Red Eléctrica, Barcelona Energy Observatory).
