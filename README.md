# MATCHSOL

IAAC MaAI · Research Studio "Operable Futures" · team 1: Breno, Sindhuja, Daria

**Homes are empty at noon. Schools are empty on weekends. MATCHSOL matches them, so every solar kilowatt-hour is used in the neighbourhood.**

A tool for Barcelona: it reads every roof, finds out what each building is and when it uses power, and matches buildings whose schedules complement each other. On weekdays, home roofs send their extra power to schools and offices; on weekends and in summer, school roofs send theirs to the homes. Spanish law allows it between buildings up to 5 km apart, with a different share for every hour. Study area: 9 blocks of the Eixample.

## Two parts

```
research_studio_team_1/
├── pipeline/   Python: from an address to panels and kWh (steps 1–5)
│   ├── step1/  find the building (Catastro, LiDAR)
│   ├── step2/  read the roof (LiDAR rules + AI model on the photo)
│   ├── step3/  lay out the panels
│   ├── step4/  shade and yield, hour by hour (PVGIS + LiDAR); the 9 blocks' roof list
│   ├── step5/  each building's use, hour by hour; sharing and co-investment groups
│   ├── web/    send results to the map; download the study area
│   ├── tests/
│   └── examples/
└── website/    MATCHSOL on the 3D map of Barcelona: matches, hourly split, money
    └── data/   our study area + one file per roof the pipeline ran
```

**The rule that keeps the map fast:** the heavy work happens once, in the pipeline, and the website shows the results. Each roof is one small file, so adding roofs doesn't slow the map down. For now the matching itself runs in the browser (well under a second for the 9 blocks); it can move to the pipeline later.

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
| Step 5: use, hour by hour | done (use predicted from Catastro; day patterns can come from Open Data BCN with `step5.bcn_data`); 5b sharing and 5c co-investment groups |
| MATCHSOL map | Matches (power lines that change direction with the day and hour), Hourly split (with the year file for the electricity company), Money, How it works. The matching runs in the browser for now (`website/match.js`), as a preview |
| Next | send every roof to the map (`python -m web.export --all`); building types from Catastro and hourly use from Open Data BCN for every building; the matching as a Python step; label roofs and train the AI model |
| Later | step 6: checks against PVGIS / Google Solar / an installer quote |
