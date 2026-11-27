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
| Institut Quatre Cantons (yellow) | 3 (was 7) | 254 m² (was 310) | 86 (was 105) | 276 m² | **all 108 CEP9 panels**, 279 m² of panel [CEP9 tender; CEP9, 27 Nov 2026] |
| Escola Pere IV (red) | 5 | 333 m² | 111 | 321 m² | **not part of CEP9** [CEP9, 27 Nov 2026]: another installation |

**Existing-panel check on the Institut (Breno, by eye on the photo, 27 Nov 2026):** of the 7 rectangles, only 3 are real panels: the long thin strip on the north-west side, the block in the middle-left and the big block in the south-east (rectangles 3, 2 and 1 on `data\roof\cep9_yellow_existing_numbered.png`). Rectangles 4, 5, 6 and 7 are not panels; they are listed in `not_panels.csv` ("checked by eye, Breno 27 Nov 2026") and stay on the roof as obstacles, like the water heaters on the red roof. Now **3 rectangles, 253.6 m², about 86 panels**, against the real **108 panels and 279 m² of panel** [CEP9 tender]: 9% less area and 20% fewer panels. Our rectangles count panels on a south-row pitch with gaps; the real plant is East-West, back to back [CEP9, 27 Nov 2026], so more panels fit on the same area. **Correction from CEP9 (email from César Ochoa, 27 Nov 2026):** all 108 panels are on the Institut, and Escola Pere IV is not part of CEP9. The old 43 red / 65 yellow split was dropped from `examples/cep9_actual.json`, whose blocks are now these 3 rectangles (`update_roof.refresh_actual_blocks`). The panel rows on the red roof belong to another installation, kept under `red_roof_what_if`.

**The rectangle check (general rule, `existing_panels.py` step 7, ASSUMPTIONS):** a rectangle is dropped when it has fewer than 6 panels (`MIN_KEEP_PANELS`), or when it is rough: LiDAR ripple above 0.10 m (`ROUGH_RIPPLE_M`, height spread after removing a tilted plane) AND more than 10% of its cells more than 0.10 m above the roof around it (`ROUGH_RAISED_SHARE`, `RAISED_M`). On the Institut, LiDAR measures of the 7 old rectangles:

| Rectangle | Real? | Panels | Ripple | Cells raised > 0.1 m | Dropped by |
|---|---|---|---|---|---|
| 1 | yes | 60 | 0.068 m | 0% | kept |
| 2 | yes | 16 | 0.067 m | 0% | kept |
| 3 | yes | 10 | 0.065 m | 0% | kept |
| 4 | no | 8 | 0.142 m | 12% | rough |
| 5 | no | 5 | 0.042 m | 0% | fewer than 6 panels |
| 6 | no | 4 | 0.167 m | 27% | fewer than 6 panels (and rough) |
| 7 | no | 2 | 0.117 m | 31% | fewer than 6 panels (and rough) |

Size alone (under 6 panels) would miss rectangle 4. A ripple window alone (0.05-0.10 m) would remove all four here, but not carry over: on the Escola Pere IV the real 75-panel block ripples 0.26 m (steeper rows) and an 18-panel block 0.01 m. With the rule above the red roof keeps its 75-, 18- and 12-panel blocks and drops a 4-panel rectangle (2.4 m above the roof) and a 2-panel one. Not tested on A160 yet (no existing-panel reading there).

**CEP9 validation, Institut only (27 Nov 2026), roof treated as empty, `cep9_540` panel, `--max-panels 108`:** with the 4 look-alikes kept as obstacles, the usable roof is 577 m² (was 659 m²) and our layout fits **85 panels (45.90 kWp) and 60,920 kWh a year** (was 97 panels before the look-alike fix), against the real 108 panels (58.32 kWp) and about 73,750 kWh [CEP9 presentation]. Per kWp we give 1,327 kWh against the real 1,265 (+5%). Our rows are spaced for no shade at a 25° sun (`layout.py`); the real plant is East-West "Delta Wing", back to back [CEP9, 27 Nov 2026]. Scaled to 108 panels (see Open items) it gives 77,404 kWh (+5.0%).

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

## Open items

- **East-West layout option in step 02/03.** CEP9's real plant is laid out East-West, "Delta Wing", at 10°, back to back with no gaps between rows [CEP9, 27 Nov 2026]. Our layout only makes south-facing rows spaced for no shade at a 25° sun, so only 85 of its 108 panels fit on the Institut. Until there is an East-West option, the CEP9 case scales the 85-panel hourly output to 108 panels (`step03_simulate_generation/scale_panels.py`, ×108/85, **ASSUMPTION**: same yield per panel): 58.32 kWp and 77,404 kWh a year, against 73,750 reported (+5.0%).
- **Existing-panel detection, done 27 Nov 2026:** the 4 false rectangles on the Institut are listed in `not_panels.csv` and the rectangle check above catches them too. Still to do: test the rule on A160 and on more roofs.

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
