# Step 08: Compare investment

**Question this step answers:** the owner pays for the panels. What is the best thing to do with the solar the host doesn't use itself, and does it pay back over 25 years?

**Roadmap:** input = installed costs, O&M, tariffs, compensation → output = incremental benefit, self-consumption ratio, payback and sensitivities.

The main tool is `roi.py` (added 27 Nov 2026). The older `investment.py` is described at the end.

## The three options

The owner pays for the panels and keeps them. The host uses what it can; that part is the same in every option. The options differ only in what happens to the **surplus**, the solar the host doesn't use:

| Option | What happens to the surplus | Where its kWh and € come from |
|---|---|---|
| **A** grid | Sold to the grid | step 04 `host_table.csv` (self-consumed and surplus kWh per hour), priced with step 06's hourly PVPC |
| **B** neighbours | Sold to a group of neighbours at (1 − discount) × the PVPC of each hour (default discount 10%); what they don't take goes to the grid as in A | step 07 `battery_agent_summary.json`, the "without battery" run; guests from step 07 `shortlist.csv` |
| **C** battery | A battery at the host stores it for the host's own later use (charged only from the panels); what is left goes to the grid as in A | step 06 `battery_sizing.json`, one row per battery size |
| **B+C** both | Neighbours and a battery | step 07 `battery_agent_summary.json`, "sizing with guests" |

All options use the same panels. `roi.py` simulates nothing: it reads what steps 04, 06 and 07 already worked out, and adds the money over 25 years.

**Battery size (C and B+C):** of the sizes step 06/07 ran (5 to 200 kWh), the one with the **highest NPV**, counting replacements. Not the one with the best "net per year".

**How guests are linked (B and B+C), `--connection`:**
- `legal`: Spanish collective self-consumption, no cable. Extra cost: a net generation meter once [IDAE Guía Autoconsumo Colectivo] and a yearly manager fee per member (host + guests).
- `wired`: a cable from the host to the guests. Extra cost: cable length × (cable + trench and repaving per metre), plus a connection kit per guest. Cable length = `--cable-m`, or by default the sum of the guests' straight-line distances × 1.3 (**ASSUMPTION**: streets aren't straight).

A "home" candidate with N dwellings counts as N guests (N kits, N members), **ASSUMPTION**. The CEP9 "30 homes" are 30 guests.

The legal route uses the **same hourly kWh** as the wired one: it assumes hourly sharing coefficients, so only the costs differ (**ASSUMPTION**). Comparing fixed and hourly shares is not part of this step.

## The formulas

**Money in, year 1**
- **own use** = kWh the host gets from the roof × PVPC of that hour (with C and B+C this includes what the battery gives back)
- **guest sales** = what the guests pay (B and B+C)
- **grid income**:
  - up to 100 kW (simplified compensation [Selectra compensación, Endesa compensación]), for each month: min(exported kWh × €0.06, € of grid energy the host still bought that month). **The rest is lost**: no cash, and it can't be taken off taxes or grid fees. This hurts hosts that are closed at weekends and in August, when they export a lot and buy little. `roi.py` reports how many € the cap throws away.
  - over 100 kW: exported kWh × the OMIE (wholesale) price of each hour, no cap.

**Cash flow, year t = 1 … 25**
```
cash_in_t  = money in, year 1 × (1 − degradation)^(t−1) × (1 + price change)^(t−1)
cash_out_t = panel upkeep + the option's yearly costs + replacements due that year
year 0     = −(panel capex + the option's capex)
```
Replacements: the inverter once in year 13; a battery every whole number of years of its life (life = the shorter of 15 years and 2,400 cycles ÷ cycles a year, from `battery_types.py`), at today's price. No battery is bought in the last year, and nothing is left over at the end (**ASSUMPTIONS**). Upkeep doesn't rise with prices.

**Results for each option**
- **NPV** = Σ (cash_in_t − cash_out_t) ÷ (1 + r)^t − capex, with r = the discount rate (5%). Money later is worth less than money now; NPV above 0 means it beats leaving the money at 5%.
- **ROI over the life** = (Σ cash_in − Σ cash_out − capex) ÷ capex. **Not discounted.**
- **simple payback** = capex ÷ (year-1 cash in − year-1 cash out)
- **discounted payback** = the first year from which the discounted running total stays at or above 0. None if the NPV is below 0.
- **money breakdown** (for a stacked bar): own use, guest sales, grid income, upkeep, replacements, capex, over the 25 years.

**Break-evens**
- **battery break-even price**: the installed €/kWh at which the best battery (C) has the same NPV as A (found by bisection). "None" = a battery doesn't pay even if free.
- **max cable**: (NPV of B wired with 0 m of cable − NPV of A) ÷ (€ per metre of cable + trench). At or below 0: wires never beat selling to the grid.

**Recommendation**: the option with the highest NPV, in one sentence.

**Sensitivity (tornado table)**: every cost in `costs.csv` that has a low and a high value is set to each in turn, and all options are run again. For each one we measure the **margin**: the NPV of the recommended option minus the best of the others. The three costs that change the margin most are listed, and "FLIPS" means a low or high value changes the recommendation.

## The costs (`costs.csv`)

One row per cost: `key, value, unit, low, high, source, status`. `status` is `sourced` or `ASSUMPTION`. Full links are in [docs/SOURCES.md](../../docs/SOURCES.md), section "Costs for the 25-year return". Keep the column names when you edit it (Sindhu will improve the values).

| Cost | Value (low-high) | Status and source |
|---|---|---|
| Panels, installed | €1,061/kWp (730-1,400) | sourced: Marblanc Solar 2025 average of 10 quotes; low APPA 2024 p.13; high is an ASSUMPTION |
| Panel upkeep | €15/kWp a year | ASSUMPTION, close to NREL ATB 2024 (US$19) |
| Panel degradation | 0.5% a year (0.4-0.7%) | ASSUMPTION, typical datasheet warranty |
| Inverter replacement | €100/kWp, once, in year 13 | ASSUMPTION |
| Grid compensation | €0.06/kWh (0.04-0.10) | sourced: Selectra (updated 9 Feb 2026); Endesa Solar Plus pays €0.06 |
| Compensation limit | 100 kW | sourced: above it you register as a producer and sell at OMIE (Selectra, Endesa) |
| Cable, buried | €24.46/m | sourced: CYPE IEL010, RZ1-K 5G10 mm² in a 75 mm tube, **without** excavation |
| Trench and repaving | €150/m (100-200) | ASSUMPTION, city street |
| Connection kit | €1,500 per guest | ASSUMPTION: protection, switchgear, meter |
| Net generation meter (legal) | €500 | ASSUMPTION; the meter is required (IDAE guide v2.1 s3.1) but no price is published |
| Manager fee (legal) | €25 per member a year (0-50) | ASSUMPTION, no figure found |
| Battery, installed | €590/kWh (460-720) | sourced: pvb.com, Europe C&I battery of ~241 kWh, updated June 2026 (vendor blog) |
| Battery upkeep | 2.5% of its cost a year | sourced: NREL ATB 2024 |
| Analysis period | 25 years | ASSUMPTION, typical panel warranty |
| Discount rate | 5% (3-8%) | ASSUMPTION |
| Price change | 0% a year (−2% to +2%) | ASSUMPTION |

Step 06's `battery_types.py` reads the battery price from this file too. To change it, edit `costs.csv`.

Other **ASSUMPTIONS** in `roi.py` (listed in SOURCES.md):
- The cap compares the compensation with the host's grid kWh × the **whole** PVPC price. The real rule caps it at the energy part of the bill only, so our cap is a bit generous.
- The cap is on the host's bill only.
- Every building is priced at PVPC, though supplies over 15 kW really pay 3.0TD (see step 06).

## How to run it

From `pipeline\`, after steps 04, 06 and 07 have run for the case (commands in the main README). For CEP9, both roofs, 540 W "best blocks" (65.88 kWp):

```powershell
cd C:\Users\breno\OneDrive\Desktop\Rooftops_RePowered_OperableFutures2026_Team1\breno_pipeline\pipeline
.venv\Scripts\python.exe -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\match\cep9_wired --sharing-dir data\sharing\cep9 --prices-dir data\prices --kwp 65.88 --connection legal --out data\roi\cep9_legal
.venv\Scripts\python.exe -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\match\cep9_wired --sharing-dir data\sharing\cep9 --prices-dir data\prices --kwp 65.88 --connection wired --out data\roi\cep9_wired
```

Other options: `--cable-m 300` (a real cable length), `--price-year 2024`, `--battery-type nmc`, `--costs` (another costs file).

**Outputs** in `--out`:
- `roi_summary.json`: all the results above, the costs used with their status, warnings, and the guests
- `roi_cashflows.csv`: `option, year, cash_in, cash_out, net, cumulative_discounted`, years 0 to 25
- `roi_line.png`: the chart below

Step 09 (`export_site_data.py`) puts both runs into the website's `site_data.json` as a `roi` block, so the page can redraw the chart and recompute the NPV with sliders.

## How to read `roi_line.png`

- **Title**: the recommendation.
- **One line per option**: the money the owner has made so far, discounted, from year 0 to year 25. Each line starts below zero at −capex, the cost on day one, and climbs as the yearly money comes in.
- **The thick line** is the recommended option.
- **The black zero line**: where a line crosses it, the option has paid back (the circle marks the discounted payback year). A line that never crosses never pays back.
- **The end of each line (year 25)** is its NPV, also written in the legend.
- **Dips**: replacements, such as the inverter in year 13 or a battery every few years.
- **The highest line at the right** is the best choice.

## Result for CEP9 (27 Nov 2026)

Both roofs, 540 W "best blocks", 65.88 kWp, 89,284 kWh a year. The school's use is an estimate, not its meter: 1,811.7 m² × 60 kWh/m², about 108,700 kWh a year [Consums Energètics Edificis 2008-2018]. The guests are the 4 real CEP9 members (fire station, Institut Maria Espinalt, Can Felipa, 30 homes) from `examples\cep9_members.csv`, with typical-year prices.

| | A grid | B neighbours | C battery | B+C |
|---|---|---|---|---|
| Battery | – | – | 5 kWh | 10 kWh |
| Capex, legal / wired | €69,899 | €70,399 / €143,212 | €72,849 | €76,299 / €149,112 |
| Year 1: own use + guests + grid | 6,620 + 0 + 1,691 | 6,620 + 3,376 + 122 | 6,843 + 0 + 1,476 | 6,704 + 3,377 + 102 |
| Lost to the compensation cap, year 1 | €679 | €0 | €691 | €0 |
| **NPV, legal** | €24,415 | **€36,231** | €15,895 | €26,295 |
| **NPV, wired** | **€24,415** | −€24,603 | €15,895 | −€34,539 |
| Simple payback, legal | 9.5 y | 8.5 y | 10.0 y | 9.3 y |

- **Legal route:** "Recommended: share with 4 neighbouring buildings (33 guests) through the legal route. Payback 8.5 years, NPV EUR 36,231, ROI 164% over 25 years. A battery pays only below EUR 70/kWh installed. Wires never beat selling to the grid."
- **Wired:** A wins. The 33 connection kits alone cost €49,500, more than B adds over A, so the wired option loses at any cable length. The default 136 m of cable is only Can Felipa's 105 m × 1.3: the other three members are listed at the host's own position in `cep9_members.csv` (not checked).
- **Battery:** the 5 kWh battery cycles about 318 times a year, so it wears out in 7.5 years and is bought 4 times in 25 years. In year 1 it adds only €8: the extra own use (+€223) is almost cancelled by lower grid income (−€215), because a smaller grid bill also lowers the compensation cap.
- **What moves the legal answer most:** the manager fee (at €50 per member a year instead of €25, the 34 members cost €1,700 a year and A wins by €164); the compensation price; the battery price.

## The older tool: `investment.py`

`investment.py` gives a yearly net value and simple payback per scenario. It has a central, low and high panel cost, and the guest-price slider formula `owner_total_at_discount` that the website uses. It has no discounting, no replacements and no compensation cap, so use `roi.py` for decisions.

```powershell
.venv\Scripts\python.exe -m step08_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp 65.88 --out data\investment\cep9
```

Its prices are in `CASES` at the top of `investment.py`, with sources in SOURCES.md. Its battery price now also comes from `costs.csv`.

**The guest-price slider:** guests pay (1 − discount) × the grid price of each hour, 10% by default. `owner_total_at_discount(result, discount)` recomputes the owner's money without re-running anything. The battery's choices hardly depend on the discount.
