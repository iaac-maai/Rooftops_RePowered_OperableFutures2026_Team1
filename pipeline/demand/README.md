# Neighbour demand (Track 2): hour by hour, for Barcelona

How much electricity each neighbour of the host roof uses, every hour of a real year.
A "neighbour" is a **consumer, not a building**: a program with its own meter(s), such as a
cafe, a supermarket, or the flats of one building. In collective self-consumption every meter
joins on its own, so several rows can sit in the same building (a cafe below, flats above).
This folder is the **baseline**: the "no AI" model that the AI forecast must beat.
It follows the method of the City Energy Analyst (CEA, ETH Zurich, MIT licence),
`use = schedule x W per m2 x floor area`, rebuilt for Barcelona:

- **Spanish calendar:** national, Catalan and Barcelona holidays 2023-2026, from the
  official calendars (`data/holidays_barcelona.csv`, a source for every date).
- **Real clock:** EU summer time (last Sunday of March to last Sunday of October).
  Outputs are in UTC, like the rest of the pipeline, with Barcelona time next to them.
- **Spanish habits:** late lunch and dinner, shops closed on Sunday, office short hours
  (8-15) in July and August, August holidays, Catalan school calendar.
- **Air conditioning and heating** from the hourly temperature of the same real year.
- **Checked against real meters:** fitted to Datadis data for postal code 08018 (Poblenou)
  2023-2024, tested on 2025.

## Quick start (from `pipeline/`, Windows)

```
pip install -r requirements.txt
python -m demand.weather --year 2024                  # once: real 2024 temperatures (needs internet)
python -m demand.run --neighbours demand\neighbours_example.csv --year 2024
python -m demand.check_bcn --energy "C:\...\energy_clean.csv" --years 2023 2024
python -m pytest tests\test_demand.py
```

Without internet, add `--weather synthetic` to `run` and `check_bcn`. That weather is
made up and is only for testing the code; never use it for results.

## Input: the neighbours file

One row per consumer (program). `neighbours_a160.csv` has the host, 10 first candidates
(370-810 m away) and 28 programs within 200 m of A160 (N11-N38: Google Maps opening hours,
plus 9 office buildings and a student residence found in the Catastro cache).
`neighbours_example.csv` is a small made-up example.

To get real floor areas and add the homes around the host from Catastro (needs internet):

```
python -m demand.catastro_fill --neighbours demand\neighbours_a160.csv --out demand\neighbours_a160_catastro.csv
```

It gives the Catastro area to rows marked `whole_building=yes`, adds a home row for the flats
in the same building as each cafe or shop, and adds the nearest residential buildings around
the host (`--homes 5`, at least `--min-flats 6` flats, within `--radius 250` m).
`--close-radius 200` also adds every residential building with at least one flat within 200 m.
`--offline` answers only from `data/catastro_cache.json`: no internet, nothing is downloaded,
and points that are not in the cache keep their estimates. The current A160 file was made with:

```
python -m demand.catastro_fill --neighbours demand\neighbours_a160.csv --out demand\neighbours_a160_catastro.csv --offline --close-radius 200
```

Running it without `--offline` asks Catastro (official service, text answers) about the new
programs too: it can then find flats above them.

| column | needed | what |
|---|---|---|
| `id` | yes | short name, becomes the column name in the output (e.g. `A160`, `N1`) |
| `type` | yes | `home`, `office`, `shop`, `supermarket`, `restaurant`, `bar`, `cinema`, `school`, `university`, `hotel`, `gym` |
| `floor_area_m2` | yes | floor area (Catastro) |
| `role` | no | `host` or `neighbour` |
| `units` | no | number of meters in the row, e.g. flats in a residential building (the summary then gives kWh per flat) |
| `whole_building` | no | `yes` if the program fills its whole Catastro plot (the host); then catastro_fill uses the Catastro area |
| `lat`, `lon` | for catastro_fill | location of the program |
| `annual_kwh` | no | yearly kWh from bills: if given, it sets the total (the shape stays) |
| `monthly_kwh` | no | 12 monthly kWh from bills, January to December, separated by `;`: each month's total is then measured |
| `hours_weekday`, `hours_saturday`, `hours_sunday` | no | real opening hours, local time: `9-14,17-21`, `20-2` (past midnight) or `closed`. Closed hours drop to the night level; open hours keep the type's shape (a restaurant still peaks at meals), at least half of peak. Empty = the type's normal hours. Round opening down and closing up (12:30-23:30 -> `12-24`) |
| `closed_august` | no | `yes` if it closes in August |
| `name`, `address`, `notes` | no | for people, not used by the model |

Holidays always follow the Sunday hours.

## One program: its whole year, hour by hour

```
python -m demand.program N05                    # by id or part of the name (Mercadona)
python -m demand.program --type bar --area 120 --weekday 8-20 --saturday 9-16 --sunday 9-16
python -m demand.program N05 --monthly-kwh ...  # (for a new program) 12 monthly bills, Jan-Dec
```

Writes `data/programs/<id>_<year>.csv` (every hour: UTC and local time, day type, temperature,
kWh) and a chart (average day by day type, two weeks, months, and the whole year as a carpet).
It also prints how exact the numbers are:

| level | based on |
|---|---|
| 1 | type only: area and hours estimated |
| 2 | Catastro floor area and the real opening hours |
| 3 | plus bills: yearly (`annual_kwh`) or monthly (`monthly_kwh`, 12 numbers) totals are measured |

Exact hour-by-hour data exists only in the program's own meter (Datadis, with the owner's consent).

## Outputs (`data/demand/`)

| file | what |
|---|---|
| `demand_baseline_hourly.csv` | one row per UTC hour (8,760, or 8,784 in a leap year): `time_utc`, `time_local`, `day_type`, then kWh for each neighbour |
| `neighbours_summary.csv` | per consumer: kWh a year (and per flat when `units` is given), kWh/m2, peak kW, share used 10-17 h (sunny hours), share used at weekends and holidays |
| `run_info.json` | year, weather source, labels |
| `typical_weeks.png` | a winter week and a summer week |

Every number is **modeled**. With `annual_kwh` the yearly total is **measured** (bills)
and the hourly shape is still modeled.

## How much each type uses: checked against Spanish sources

Each type's watts per m2 start from the City Energy Analyst tables (Swiss standard SIA 2024),
then the whole type is scaled so its yearly use per m2 matches a Spanish or Barcelona source
(2024 real weather). Scaling a type keeps its day shape, which is fitted to 08018.

| type | kWh/m2 a year | source |
|---|---|---|
| home | 35 (about 2,970 kWh per flat) | real Barcelona homes 2024: Datadis residential total (energy_clean.csv) / 704,600 households (Barcelona padro) |
| office | 100 | typical Spanish office (Repsol business advice, sector average) |
| shop | 131 | inside the Barcelona benchmark for pharmacies (good: 70-160) |
| supermarket | 300 | inside the Barcelona food-shop benchmark (185-430); **weakest source** |
| restaurant, bar | 200 | near the Barcelona food benchmark; **no source for restaurants or bars alone** |
| cinema | 100 | Barcelona benchmark for leisure and culture (good: 85-105) |
| school | 25 | audit of 17 schools in El Prat de Llobregat (1,075 MWh / 42,560 m2) |
| university | 75 | UPF Campus del Poblenou, 2018-2019 (77 and 74 kWh/m2) |
| hotel | 125 (about 6,250 kWh per room) | IDAE survey of 153 Spanish hotels: 6,150 kWh per room a year in 4-5 star hotels, at about 50 m2 per room (the ZT hotel: Catastro 7,602 m2 for 150 rooms). Repsol gives only 30-50 kWh/m2 for an average hotel: **uncertain** |
| gym | 100 | electricity in Madrid municipal sports centre audits (74-227 kWh/m2; Gimnasio Moscardo 97, La Chopera 89): **weak source** |

Hotels: AC and heating run at night too (`hvac_min_on` 0.8 in use_types.csv), because guests
sleep there; area = rooms x 50 m2. Gyms: Spanish peaks (7-9, 13-14, 18-21), quieter in August.

The Barcelona benchmarks are from the city's energy-performance sheet for establishments under
500 m2 (barcelona.cat/barcelonasostenible, 2023). With real opening hours a program's own value
moves around these (a cafe open 9-16 uses less than one open all day).

## How one hour is computed

```
share    = schedule[type][day type][local hour]                  data/schedules.csv (0..1)
internal = area * ((appliances + lighting) * share * month + always_on) / 1000
on       = 0.15 + 0.85 * (how far the building is above its night level)
T24      = mean outdoor temperature of the last 24 hours (buildings store heat)
ac_heat  = area * (cooling * max(0, T24 - t_cool) + heating * max(0, t_heat - T24)) * on / 1000
kWh      = internal + ac_heat
```

All values are in `data/use_types.csv` (W/m2, AC, heating, which calendar), `data/schedules.csv`
(72 rows: weekday, Saturday, Sunday x 24 hours, same layout as CEA) and `data/monthly.csv`.
They are plain tables: open them in Excel to change a number.

## The check against real Barcelona data (08018)

The city's open data (Datadis meters) has, for every day and postal code, the use of homes
and of services in 4 time bands. No buildings and no hours, so it cannot train a model,
but it tests the pattern. Note: the values are **kWh**, not MWh as the dataset title says.

The home schedules, the services base load and the AC settings were **fitted on 2023-2024**,
so those years match closely on purpose. **2025 (January-November) was not used for fitting**:
it is the honest test. All with real hourly weather (Open-Meteo ERA5).

| use vs a normal weekday | homes real 2025 | homes model | services real 2025 | services model |
|---|---|---|---|---|
| Saturday | 0.990 | 0.917 | 0.804 | 0.820 |
| Sunday | 0.981 | 0.935 | 0.724 | 0.714 |
| Holiday | 0.918 | 0.882 | 0.758 | 0.705 |

- **Split of the day over the 4 time bands:** off by about 1 percentage point on average.
  Services are a little too high in the afternoon (12-18 h: 0.328 vs 0.315 on weekdays)
  and too low in the morning.
- **Services hold up in 2025.** Holidays are about 5% too low.
- **Homes do not fully hold up:** in 2025 their weekends were almost like weekdays, unlike
  2023-2024, so the home weekend level is uncertain (about 5-8%).
- **Months:** the model is off by 0.09 (services) and 0.13 (homes) on average. The real data
  itself changes more than that from one year to the next (0.11 and 0.17), so months cannot be
  tuned further with this data. Services' summer peak is a little low (July 1.10 vs about 1.22).

`check_bcn` writes the full table and a chart (`data/demand/check_08018.png`).

What it taught us:
- **Holidays matter.** In 08018, services use 25% less on a holiday than on a normal
  weekday, about the same as a Sunday. Treating holidays as workdays would be wrong by a quarter.
- **Homes use less at weekends and holidays** (people go out or leave town), not more.
- **Services never switch off.** At night they still use about two thirds of their average
  hour, about half of a daytime hour (servers, fridges, ventilation). So the model keeps a large always-on load for
  offices and shops. A real host or neighbour may be lower: their bills will tell.

Limits (be honest about them in the presentation):
- Homes are compared directly. Services are compared with an **assumed mix** for 08018
  (50% offices, 12% shops, 10% university, 8% restaurants, 7% bars, 7% schools,
  5% supermarkets, 1% cinema; change it with `--mix`). Each type on its own is not tested.
- The monthly pattern in the open data changes a lot from year to year (meters moving
  between sectors), so it is a weak test.

## Next steps

1. Run with the real neighbours table and the real weather of the decision year.
2. Add `annual_kwh` wherever there are bills.
3. The AI model (trained on GoiEner, real Spanish meters) must beat this baseline on
   buildings it has not seen. This baseline is scenario S2 ("shares from schedules, no AI").

## Sources

- Method and starting W/m2: City Energy Analyst, `cea/databases/CH` (SIA 2024 values), MIT licence.
- Holidays: Generalitat de Catalunya (Ordre EMT/81/2022, EMT/85/2024, EMT/66/2025),
  Ajuntament de Barcelona (Gaseta Municipal, calendari de festius).
- Real data: Open Data BCN `consum-electricitat-bcn` (Datadis).
- Weather: Open-Meteo historical archive (ERA5).
- Programs within 200 m: Google Maps (names, opening hours), Catastro cache (use, floors, area, flats),
  NH Hotels website (129 rooms), Travelocity (ZT hotel, 150 rooms), Urban Sports Club / Wellhub
  (Workshop Fitness, 1,800 m2), Diario Design 2012 (Almogavers Business Factory).
- Hotels: energias-renovables.com on the IDAE hotel survey; Repsol, "consumo electrico de un hotel".
- Gyms: Ayuntamiento de Madrid, energy audits of municipal sports centres.
