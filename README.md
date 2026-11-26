# Rooftops RePowered

IAAC MaAI · Research Studio "Operable Futures" · team 1: Breno, Sindhuja, Daria

Solar co-investment communities in the Eixample: our pipeline reads every roof (LiDAR, shade, energy), panels go on the 10 roofs with the most energy per panel, and neighbours within 500 m co-invest and buy a fixed share of the output (RD 244/2019).

## Two parts

```
research_studio_team_1/
├── pipeline/   Python: from an address to panels and kWh (steps 1–5)
│   ├── step1/  find the building (Catastro, LiDAR)
│   ├── step2/  read the roof (LiDAR rules + AI model on the photo)
│   ├── step3/  lay out the panels
│   ├── step4/  shade and yield, hour by hour (PVGIS + LiDAR); the 9 blocks' roof list
│   ├── step5/  each building's use; sharing groups; co-investment communities (5c)
│   ├── web/    send results to the map; download the study area
│   ├── tests/
│   └── examples/
├── website/    the 3D map: the communities, with arrows from each host roof to its guests
│   └── data/   our study area + one file per roof the pipeline ran + the communities
└── website_matchsol/   the hourly version of the idea (MATCHSOL), kept for later
```

**The rule that keeps the map fast:** the heavy work happens once, in the pipeline. The website only shows the results. Each roof is one small file, opened only when someone clicks that roof, so adding roofs doesn't slow the map down.

## Quick start

**See the map:** open `website/index.html` with VS Code's Live Server (details in [website/README.md](website/README.md)).

**Run the pipeline** (details in [pipeline/README.md](pipeline/README.md)):

```
cd pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m step4.weather
python -m step4.roof_test_set --out data\roof_test_set
python -m web.buildings
python -m step4.batch data\roof_test_set\roof_test_set.csv --laz-dir data\lidar --out data\yield_all --web
python -m step5.communities --yield-dir data\yield_all
python -m web.communities
```

## Where the project stands

| | Status |
|---|---|
| Step 1: find the building | done |
| Step 2: read the roof, LiDAR | done; tested on Roger de Llúria 56, Aragó 284 and 308 |
| Step 2: read the roof, AI model | code ready; needs labelled roofs to train |
| Step 3: panel layout | done |
| Step 4: shade and yield | done; tested on Bruc 59 and Diputació 311 |
| Roof list of the 9 blocks | done (`step4.roof_test_set`) |
| Step 5: use, sharing groups, co-investment communities (5c) | done (use predicted from Catastro) |
| 3D map | Communities on the 9 blocks, coloured like step 5c's map (the rest of the city stays the city's red model), arrows from host roofs to guests, the table; click a building to see its community. Read from step 5c's map until `website/data/communities.json` is in |
| Next | send step 5c's communities (`python -m web.communities`) and every roof (`python -m web.export --all`) to the map; label roofs and train the AI model |
| Later | step 6: checks against PVGIS / Google Solar / an installer quote |

## breno_pipeline: the roof-surplus pipeline (V2)

`breno_pipeline/` is Breno's V2 tool, brought in with its full git history (`git subtree`). It sits in its own folder, so nothing above it changed. It follows one host roof through 9 steps, from the building to the money for the owner and the neighbours who use the spare solar:

| Step | What it does |
|---|---|
| 01 | pick the host: address, Catastro footprint (LiDAR if Catastro has none), cadastral refs, known gaps |
| 02 | read the roof from LiDAR + photo: usable area, existing panels, panel layouts |
| 03 | shade + PVGIS: hourly solar for each layout |
| 04 | the host's own hourly use, and the spare solar |
| 05 | the neighbours' hourly use (baseline profiles + Open Data BCN) |
| 06 | real hourly prices, price forecast, battery size |
| 07 | which nearby buildings share the energy, and the battery agent |
| 08 | owner and guest money, with and without a battery |
| 09 | one data file for its website |

Test cases: **CEP9** (Quatre Cantons schools, Poblenou; checked against the real 108-panel install) and **A160** (Almogàvers 160 offices).

**Run it** (Windows PowerShell, from the top of this repo):

```
cd breno_pipeline\pipeline
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest tests
```

The step-by-step commands are in [breno_pipeline/pipeline/README.md](breno_pipeline/pipeline/README.md) and in each step's own README. To see its website, follow [breno_pipeline/website/README.md](breno_pipeline/website/README.md).

**Sources:** every number has a source in [breno_pipeline/docs/SOURCES.md](breno_pipeline/docs/SOURCES.md) or is marked **ASSUMPTION** in the code.

Not included: LiDAR tiles and other downloads (`pipeline\data\`), the `.venv` and caches. Each person downloads their own, as the step READMEs explain.
