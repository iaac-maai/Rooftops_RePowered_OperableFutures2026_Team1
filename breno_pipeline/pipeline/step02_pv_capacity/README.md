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
| Institut Quatre Cantons (yellow) | 4 (was 7) | 268.5 m² (was 310) | 91 (was 105) | 291 m² | **all 108 CEP9 panels**, 279 m² of panel [CEP9 tender; CEP9, 27 Nov 2026] |
| Escola Pere IV (red) | 5 | 333 m² | 111 | 321 m² | **not part of CEP9** [CEP9, 27 Nov 2026]: another installation |

**Existing-panel check on the Institut (Breno, by eye on the photo, 27 Nov 2026):** of the 7 rectangles on `data\roof\cep9_yellow_existing_numbered.png`, 4 are real panels: the big block in the south-east (1), the block in the middle-left (2), the long strip on the north-west side (3) and the thin strip in the upper middle (5). Rectangles 4, 6 and 7 are not panels. They are listed in `not_panels.csv` ("checked by eye, Breno 27 Nov 2026") and stay on the roof as obstacles, like the water heaters on the red roof. Now **4 rectangles, 268.5 m², about 91 panels**, against the real **108 panels and 279 m² of panel** [CEP9 tender]: 4% less area and 16% fewer panels. Our rectangles count panels on a south-row pitch; the real plant is East-West, back to back [CEP9, 27 Nov 2026], so more panels fit on the same area. **Correction from CEP9 (email from César Ochoa, 27 Nov 2026):** all 108 panels are on the Institut, and Escola Pere IV is not part of CEP9. `examples/cep9_actual.json` lists these 4 blocks (`update_roof.refresh_actual_blocks`). The panel rows on the red roof belong to another installation, kept under `red_roof_what_if`.

**The rectangle check (general rule, `existing_panels.py` step 7, ASSUMPTIONS):** a rectangle is dropped when it is **rough**: LiDAR ripple above 0.10 m (`ROUGH_RIPPLE_M`, height spread after removing a tilted plane) AND more than 10% of its cells more than 0.10 m above the roof around it (`ROUGH_RAISED_SHARE`, `RAISED_M`). The size minimum is only the detector's own (2 panels). LiDAR measures of the 7 rectangles:

| Rectangle | Real? | Panels | Ripple | Cells raised > 0.1 m | Result |
|---|---|---|---|---|---|
| 1 | yes | 60 | 0.068 m | 0% | kept |
| 2 | yes | 16 | 0.067 m | 0% | kept |
| 3 | yes | 10 | 0.065 m | 0% | kept |
| 5 | yes | 5 | 0.042 m | 0% | kept |
| 4 | no | 8 | 0.142 m | 12% | dropped: rough |
| 6 | no | 4 | 0.167 m | 27% | dropped: rough |
| 7 | no | 2 | 0.117 m | 31% | dropped: rough |

The rough test alone separates them. A size minimum cannot: the real strip 5 (5 panels, one row) is smaller than the false rectangle 4 (8 panels). A ripple window alone does not carry over either: on the Escola Pere IV the real 75-panel block ripples 0.26 m (steeper rows) and an 18-panel block 0.01 m; the rough test keeps both. Not tested on A160 yet (no existing-panel reading there). The hand list (`not_panels.csv`) is kept as Breno's check.

**CEP9 validation, Institut only (27 Nov 2026), 540 W, roof treated as empty, rectangles 4, 6 and 7 as obstacles (usable roof 610.5 m²).** Real: 108 panels, 58.32 kWp, 73,750 kWh a year [CEP9 presentation]; real rectangles 1, 2, 3 and 5 = 268.4 m².

| Layout | Edge setback | Panels | vs 108 | kWh a year | vs 73,750 | kWh per kWp | IoU with the real rectangles | Panels inside them |
|---|---|---|---|---|---|---|---|---|
| South rows, fill the roof | 1 m | 90 | −17% | 64,509 | −13% | 1,327 | 0.34 | 48 |
| South rows, neat | 1 m | 54 | −50% | 38,621 | −48% | 1,324 | 0.38 | 46 |
| South rows, neat + one-deep rows | 1 m | 81 | −25% | 58,009 | −21% | 1,326 | 0.35 | 46 |
| **East-West, fill the roof** | 1 m | **103** | −5% | 70,129 | −5% | **1,261** | 0.43 | 62 |
| East-West, neat | 1 m | 62 | −43% | 41,981 | −43% | 1,254 | 0.47 | 56 |
| East-West, best | 1 m | 62 | −43% | 41,981 | −43% | 1,254 | 0.47 | 56 |
| **East-West, neat + one-deep rows (CEP9 default)** | 1 m | **91** | **−16%** | 62,150 | −16% | 1,265 | 0.44 | 59 |
| East-West, best + one-deep rows | 1 m | 76 | −30% | 51,899 | −30% | 1,265 | 0.46 | 56 |
| South rows, fill the roof | 0.5 m (test) | 101 | −6% | 72,248 | −2% | 1,325 | 0.39 | 59 |
| East-West, fill the roof | 0.5 m (test) | 116 | +7% | 78,683 | +7% | 1,256 | 0.45 | 67 |
| East-West, neat | 0.5 m (test) | 75 | −31% | 50,853 | −31% | 1,256 | 0.50 | 62 |
| East-West, neat + one-deep rows | 0.5 m (test) | 104 | −4% | 70,056 | −5% | 1,247 | 0.48 | 66 |

What it shows:
- **East-West matches the real yield per kWp:** 1,261-1,265 kWh per kWp against the real 1,265, and against 1,327 for south rows (−5%: the half facing 39° gets less sun).
- **The East-West pattern reproduces the real blocks.** Laid inside each real rectangle (with 0.2 m tolerance for the rectangles' exact snapped sizes), it fits **60, 16 and 10** panels in blocks 1, 2 and 3, the same as the photo. Block 5 is 1.8 m deep, so only one half-row of 3 panels fits; its real panels may run the other way. South rows fit 48, 12, 8 and 3.
- **With the default 1 m setback, East-West neat + one-deep rows gives 91 panels (−16%)**, outside the 10% goal. The rest of the gap is the setback. The real blocks 1 and 3 run to about 0.2 m from the building outline (block 2: 1.0 m, block 5: 2.4 m), and the 1 m setback leaves part of them empty. We found no rule to cite for the setback (searched the CTE fire guidance and installer guides: they mention firefighter access and safety distances, without a figure), so 1 m stays the default and 0.5 m is only shown as a test (104 panels, −4%).

```
python -m step03_simulate_generation.shade_yield --lat 41.404361 --lon 2.2 --laz-dir data\lidar --usable data\roof\cep9_yellow_usable.geojson --panel cep9_540 --layout neat --case cep9 --out data\pv\cep9_institut_ew
```

The picture `data\pv\cep9_institut_layout_check.png` shows East-West neat + one-deep rows on the photo, with the two halves of each pair in two colours and the real rectangles in blue.


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

- **East-West layout option: done (27 Nov 2026),** see `layout.lay_out_ew` and step 03 `--orient eastwest`; the CEP9 case uses it by default through its case file. Still open: whether CEP9 should use a smaller edge setback (the real blocks run to about 0.2 m from the outline), which needs a source or CEP9's plan.
- **Existing-panel detection, done 27 Nov 2026:** rectangles 4, 6 and 7 on the Institut are listed in `not_panels.csv` and the rough test catches them too; strip 5 is real. Still to do: test the rule on A160.

## East-West layout (`layout.lay_out_ew`, step 03 `--orient eastwest`)

Panels go in **back-to-back pairs along the building**: one half faces the building's south-side direction (219° on the Institut), the other the opposite way (39°), both at 10°, so the high edges meet at a ridge. Pattern: **pair, gap, pair, gap ...** (Breno, from the photo, 27 Nov 2026). No gap is left for shade, because at 10° the two halves lean against each other.

| Number | Value | Source |
|---|---|---|
| Tilt | 10° | CEP9's real plant, "Delta Wing" [CEP9, email from César Ochoa, 27 Nov 2026] |
| Gap at the ridge | 0 m | back to back [CEP9, 27 Nov 2026; photo] |
| Gap after every pair | **0.40 m** | **measured on ICGC orthophoto / LiDAR, ~0.25 m per pixel, approximate**: real block 1 repeats every 2.63 m on the photo and 2.66 m in the LiDAR, minus the pair's depth 2 × 1.134 m × cos 10° = 2.234 m. Check: 5 pairs in block 1's 12.79 m. Racking makers put the walkway in this gap: 150 mm [Schletter FixGrid East-West manual](https://portal.segensolar.co.za/reseller/docs/03_20201220_installation_guide_FixGrid_EW_FixGrid_EW.PDF), 8 in = 0.20 m [Unirac RMDT manual](https://ladpw.org/bsd/lib/fp/Small%20Residential%20Rooftop%20Solar%20Energy%20Systems/LA%20County%20Recognized%20UL%202703%20Racking%20Systems/Unirac%20RMDT%20Ballast%20System%20Installation%20Guide.PDF) |
| Extra walkways every few pairs | none | none on the photo; none in the manuals above |

The yield model uses each half's own azimuth. In step 03's neat and best blocks, each half is judged against the best panels facing the same way, so the half that faces away from the sun is not called "weak" by design. With `--one-deep-rows 4`, a single row of at least 4 panels also counts as a block (ASSUMPTION: the real strips 3 and 5 are one row deep); in East-West a pair is already 2 rows deep.

**Default only for the CEP9 case:** `step01_select_host/cases/cep9.json` has `"layout": {"orient": "eastwest", "one_deep_rows": 4}` on the Institut roof, and step 03 reads it with `--case cep9`. Every other case keeps south rows. The code has no CEP9 special case.

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
