# Step 02: Evaluate PV capacity

**Roadmap:** input = ICGC LiDAR + imagery, obstacle masks, panel specification, exclusion rules → output = usable m², panel count, installed kWp, layout and confidence.

| File | What it does | From V1 |
|---|---|---|
| `lidar_roof.py` | Groups 0.5 m LiDAR cells into flat surfaces; anything sticking out is an obstacle; marks lower roofs (>7 m below the main roof) and roofs on the exclusion list | step2, unchanged |
| `grid.py` | The 0.5 m grid helper | step2, unchanged |
| `ortho.py` | Downloads the ICGC orthophoto (only for the preview picture) | step2, unchanged |
| `read_roof.py` | Address → usable area, obstacles, pictures. **LiDAR only** | step2, AI model removed |
| `layout.py` | Panel rows on the usable area, 10° tilt. Panels come from `panels.csv`: `residential_420` (420 W, 1.722 × 1.134 m, ASSUMPTION) or `cep9_540` (540 W, 2.279 × 1.134 m, from the CEP9 tender). Row direction: `--orient building` (default), `south` or `search`, see below | step3, extended |

Usable area = free surface minus 1 m along the edge and 0.5 m around obstacles, keeping pieces where at least one panel fits.

## Existing panels vs room for new ones (`existing_panels.py`, 21 and 26 Nov 2026)

Step 02 now reads every roof from the step 01 footprint, the LiDAR **and** the orthophoto. Panels already on the roof are found on the photo as neutral grey or blue, textured areas (the bare roof here is warm-coloured and smooth). Then they are checked against the LiDAR: a panel block must sit on a roof surface, not on a wall. The LiDAR also gives each block's "ripple", meaning the stripes that tilted panel rows make. All limits are ASSUMPTIONS, tuned by eye on the two CEP9 roofs.

**Rectangles (26 Nov 2026).** Real panels sit in neat rectangular groups, so each panel blob becomes one or more rectangles (`fit_rectangles`):
1. The angle is the roof's longest edge or that + 90°, whichever the strongest edges in the photo follow (checked with a structure tensor on the photo).
2. In that frame, the blob is cut where a row or column holds less than 50% of the fullest one, so an L gives two rectangles.
3. Each part is boxed and snapped to whole panels (pitch along the row = panel length + 0.05 m; across = panel width x cos 10° + 0.18 m), when that changes its area by less than 15%; otherwise the fitted size is kept and counted by area. The panel may lie with its long side along or across the rectangle; the one that fits better is kept.
4. Rectangles closer than 0.5 m are merged (if the joint box is not mostly empty); those under 2 panels or under 60% blob pixels are dropped.

The 50% cut, 0.5 m merge, 60% fill and 15% snap are ASSUMPTIONS. The 0.18 m between existing rows was measured once on the Institut photo (the brightness repeats every 1.30 m across the rows); the photo is about 0.25 m per pixel, so it is approximate.

Each reading reports:
- `existing_panels_m2` (rectangle area) and `existing_panels_estimate` (panels per row x rows, summed), plus `existing_panels_pixels_m2` (the raw pixels, for comparison) and every rectangle under `existing_panel_rectangles`;
- `usable_empty_roof_m2`, the roof as if no panels were there;
- `usable_new_only_m2`, room for new panels beside the existing ones (the rectangles are taken out).

`--roof-state empty` (default) or `existing` picks which one goes to step 03. `<out>_existing_panels.geojson` holds one feature per rectangle; `<out>_existing_panels_pixels.geojson` keeps the raw pixels for debugging; the preview outlines the rectangles in dark blue.

**CEP9, 540 W panels (`--panel-wp 540`):**

| Roof | Rectangles | Area | Panels estimate | Old pixel area | Real |
|---|---|---|---|---|---|
| Institut Quatre Cantons (yellow) | 7 | 310 m² | 105 | 301 m² | **all 108 CEP9 panels**, 279 m² of panel [CEP9 tender; CEP9, 27 Nov 2026] |
| Escola Pere IV (red) | 5 | 333 m² | 111 | 321 m² | **not part of CEP9** [CEP9, 27 Nov 2026]: another installation |

On the Institut the rectangles land on the real blocks, and 105 panels is within 3% of the real 108. **Correction from CEP9 (email from César Ochoa, 27 Nov 2026):** all 108 panels are on the Institut, and Escola Pere IV is not part of CEP9, as the tender (p5, p8) already said. The old 43 red / 65 yellow split (Breno's Google Earth count) was dropped from `examples/cep9_actual.json`. The panel rows on the red roof belong to another installation; they are kept in that file under `red_roof_what_if`, for the extra case "what if the school next door joined".

**CEP9 validation, Institut only (27 Nov 2026), roof treated as empty, `cep9_540` panel, `--max-panels 108`:** our layout fits **97 panels (52.38 kWp) and 69,508 kWh a year**, against the real 108 panels (58.32 kWp) and about 73,750 kWh [CEP9 presentation]: 11 panels and 5.8% of the energy short, while per kWp we give 1,327 kWh against the real 1,265 (+5%). Our rows are spaced for no shade at a 25° sun (`layout.py`); the real rows are packed tighter. Other settings don't reach 108 either: 98 keeping shaded panels (`--max-shade 1`), 100 in portrait, 97 with `--orient search`.

```
python -m step03_simulate_generation.shade_yield --lat 41.404361 --lon 2.2 --laz-dir data\lidar --usable data\roof\cep9_yellow_usable.geojson --panel cep9_540 --max-panels 108 --out data\pv\cep9_institut
```

**Extra case "what if the school next door joined" (both roofs, roof treated as empty, `cep9_540` panel):** 540 W neat blocks give red 70 + yellow 63 = 133 panels and 96,731 kWh. (With the old 2.28 x 1.13 m size it was 61 + 63 = 124.) This used to be called the CEP9 validation; it is not, because the red roof is not part of CEP9.

Two rules on the red roof, both from Breno (21 Nov 2026):
- The light-blue rows are mostly panels. The two northernmost rows are **solar water heaters**: they are listed in `not_panels.csv`, are not counted as panels, and stay on the roof as obstacles.
- The **south-east part** (464 m²) has no panels in reality, probably kept free for a future extension (ASSUMPTION, not confirmed). For the validation it is left out with `--reserved examples\cep9_reserved.geojson`. Without it the red roof gets 92 panels and both roofs 155.

To run it:

```
python -m step02_pv_capacity.read_roof "Camí Antic de València 35, Barcelona" --laz-dir data\lidar --reserved examples\cep9_reserved.geojson --out data\roof\cep9_red --panel-wp 540
python -m step02_pv_capacity.read_roof --lat 41.404361 --lon 2.2 --laz-dir data\lidar --out data\roof\cep9_yellow --panel-wp 540
python -m step03_simulate_generation.shade_yield "Camí Antic de València 35, Barcelona" --laz-dir data\lidar --usable data\roof\cep9_red_usable.geojson --panel cep9_540 --layout neat --out data\pv\cep9_v2\red
python -m step03_simulate_generation.shade_yield --lat 41.404361 --lon 2.2 --laz-dir data\lidar --usable data\roof\cep9_yellow_usable.geojson --panel cep9_540 --layout neat --out data\pv\cep9_v2\yellow
python -m step03_simulate_generation.combine_roofs --roof red=data\pv\cep9_v2\red_yield.json --roof yellow=data\pv\cep9_v2\yellow_yield.json --out data\pv\cep9_v2\cep9
python -m step09_publish_report.update_roof --yield examples\cep9_both\cep9_yield.json --actual examples\cep9_actual.json --label "..." --below-note "..."
```

```
python -m step02_pv_capacity.read_roof "Carrer de Jordi Girona 29, Barcelona" --laz-dir data\lidar --out nexus2
```

Outputs: `nexus2.json` (numbers), `nexus2_usable.geojson` (QGIS), `nexus2_preview.png`, `nexus2_photo.png`, `nexus2_height.png`.

Panel count and kWp come out of step 03 (`shade_yield` lays the panels and drops shaded ones).

**Roofs already in use** (sports courts, gardens): list them in `data\roof_exclusions.csv` (`refcat,reason`) and they get 0 usable m².

**Left out from V1:** the U-Net photo model (`model.py`, `train.py`, `dataset.py`). Midterm reviewers said this step does not need AI. It is still in the V1 repository if we want it back.

## Which way the panel rows point (`--orient` in step 03)

A flat roof is a free choice: rows can follow the building's walls, face due south, or sit at any angle in between. Rows square to the walls waste the least roof, but turned a few degrees they sometimes fit more panels. Panels turned away from south make a little less (at 10° tilt, 45° off south costs about 2.5%: an ASSUMPTION, `yield_factor` in `layout.py`).

| `--orient` | What it does |
|---|---|
| `building` (default, as in V1) | rows along the building edge nearest south |
| `south` | rows facing due south |
| `search` | lays the panels out every 5° from -45° to +45° around the building's axis (and at due south), scores each by panels × sun factor, keeps the best, and prints the table |

**Test on the CEP9 roof (15 Nov 2026, usable area from step 02, building axis 136°):** the panel count moves between 194 and 207 (420 W) and between 136 and 152 (540 W) as the rows turn. The best is due south (+45° from the building axis) with 207 panels of 420 W, against 201 along the building axis. So on this roof turning the rows gains about 3%, not the large gain expected; other roofs may differ. Run `--orient search` on the A160 roof to compare. To be checked against another tool: see the Google Solar slot below.

## Checking our layout against another tool

The website can show a second tool's panel plan next to ours (`export_site_data --compare-image <file> --compare-caption "..."`). The best candidate is Google's Solar API / Project Sunroof view of the same roof. We have not got one yet: it needs a screenshot or an API key from a team member (do not paste the key in the repository).

**Test sites and LiDAR tiles.** Poblenou: sheets **433583 and 433584** (CEP9 school) and **432583** (A160 office), as named in `sites/*.json`. Sheet 433584 has no building class, so the code treats its class-1 points as building. The old Eixample sheets 430582 and 430583 belong to V1 and are not used by the website. UPC Campus Nord needs its sheets listed in `sites/upc_campus_nord.json` (still marked CHECK).
