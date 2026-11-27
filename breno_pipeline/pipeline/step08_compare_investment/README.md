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
| **REF** CEP9 real terms | For reference only, never recommended. Each member gets a fixed share of every hour's output, given for free (CEP9: host 0.30, Maria Espinalt 0.13, Can Felipa 0.13, fire station 0.14, 30 homes 0.30 [CEP9, 27 Nov 2026]). The owner gets only the host's own share × PVPC, plus compensation for the part of that share the host doesn't use. Legal-route costs apply | step 07 `agreed_shares_summary.json` (`--agreed-dir`): the host's share; host kWh = `host_table.csv` × that share |

All options use the same panels. `roi.py` simulates nothing: it reads what steps 04, 06 and 07 already worked out, and adds the money over 25 years.

**Battery size (C and B+C):** of the sizes step 06/07 ran (5 to 200 kWh), the one with the **highest NPV**, counting replacements. Not the one with the best "net per year".

**How guests are linked (B and B+C), `--connection`:**
- `legal`: Spanish collective self-consumption, no cable. Extra cost: a net generation meter once [IDAE Guía Autoconsumo Colectivo], and a yearly manager fee **per member (supply point)**, because each home signs the sharing agreement. A "home" candidate with N dwellings is N members; members = host + guests. The CEP9 "30 homes" are 30 members, so CEP9 has 34. CEP9 itself pays **no** manager fee: the Barcelona Energy Agency prepares the coefficient file [CEP9, 27 Nov 2026]. Use `--manager-fee-eur-per-member 0` for that.
- `wired`: a cable from the host to the guests. Extra cost: cable length × (cable + trench and repaving per metre), plus **one connection kit per guest building**: a block of 30 homes is one building, one kit. Cable length = `--cable-m`, or by default the sum of the guests' straight-line distances × 1.3 (**ASSUMPTION**: streets aren't straight).

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
| Grid compensation | €0.06/kWh (0.04-0.10) | sourced: Selectra (updated 9 Feb 2026); Endesa Solar Plus pays €0.06; read 26 Nov 2026 |
| Compensation limit | 100 kW | sourced: above it you register as a producer and sell at OMIE (Selectra, Endesa) |
| Cable, buried | €24.46/m | sourced: CYPE IEL010, RZ1-K 5G10 mm² in a 75 mm tube, **without** excavation; read 26 Nov 2026 |
| Trench and repaving | €150/m (100-200) | ASSUMPTION, city street |
| Connection kit | €1,500 per guest building | ASSUMPTION: protection, switchgear, meter |
| Net generation meter (legal) | €500 | ASSUMPTION; the meter is required (IDAE guide v2.1 s3.1) but no price is published |
| Manager fee (legal) | €25 per member a year (0-50) | ASSUMPTION, no figure found. CEP9 pays €0 [CEP9, 27 Nov 2026]: `--manager-fee-eur-per-member 0` |
| Battery, installed | €590/kWh (460-720) | sourced: pvb.com, Europe C&I battery of ~241 kWh, updated June 2026 (vendor blog); read 26 Nov 2026 |
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

From `pipeline\`, after steps 04, 06 and 07 (including `agreed_shares`) have run for the case. The commands are in `step09_publish_report/README.md`. For CEP9, Institut roof only, 97 panels of 540 W (52.38 kWp):

```powershell
cd C:\Users\breno\OneDrive\Desktop\Rooftops_RePowered_OperableFutures2026_Team1\breno_pipeline\pipeline
.venv\Scripts\python.exe -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\match\cep9_wired --sharing-dir data\sharing\cep9 --agreed-dir data\agreed\cep9 --prices-dir data\prices --kwp 52.38 --connection legal --out data\roi\cep9_legal
.venv\Scripts\python.exe -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\match\cep9_wired --sharing-dir data\sharing\cep9 --agreed-dir data\agreed\cep9 --prices-dir data\prices --kwp 52.38 --connection legal --manager-fee-eur-per-member 0 --out data\roi\cep9_legal_fee0
.venv\Scripts\python.exe -m step08_compare_investment.roi --host-dir data\host\cep9 --battery-dir data\battery\cep9 --match-dir data\match\cep9_wired --sharing-dir data\sharing\cep9 --agreed-dir data\agreed\cep9 --prices-dir data\prices --kwp 52.38 --connection wired --out data\roi\cep9_wired
```

Other options:
- `--manager-fee-eur-per-member 0` replaces the manager fee in `costs.csv` for this run
- `--cable-m 300` gives a real cable length
- `--price-year 2024`
- `--battery-type nmc`
- `--costs` uses another costs file
- leave out `--agreed-dir` to drop the REF row

**Outputs** in `--out`:
- `roi_summary.json`: all the results above, the costs used with their status, warnings, and the guests
- `roi_cashflows.csv`: `option, year, cash_in, cash_out, net, cumulative_discounted`, years 0 to 25
- `roi_line.png`: the chart below

**Shared copies:** `data\` is not in git, so the CEP9 results are copied to [`examples/roi/`](../examples/roi/) (`roi_summary.json` and `roi_line.png` of each run):
- `examples\roi\cep9_legal\`: legal route, manager fee €25 per member
- `examples\roi\cep9_legal_fee0\`: legal route, no manager fee (CEP9's real case)
- `examples\roi\cep9_wired\`

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

**The case: Institut Quatre Cantons roof only.** CEP9 told us on 27 Nov 2026 that all 108 panels are on the Institut and that the Escola Pere IV next door is not part of CEP9 [CEP9, 27 Nov 2026].
- **Panels:** our step 03 layout fits only **97 of the 540 W panels, 52.38 kWp, 69,508 kWh a year**. The real system is 108 panels, 58.32 kWp and about 73,750 kWh [CEP9 presentation]. Our rows are spaced for no shade at a 25° sun; the real rows are packed tighter. So we are 11 panels and 5.8% of the energy short, but per kWp we give 1,327 kWh against the real 1,265 (+5%). Everything below uses `--kwp 52.38`, so cost and output match.
- **Demand and prices:** the school's use is an estimate, about 108,700 kWh a year [Consums Energètics Edificis 2008-2018]. The guests are the 4 real CEP9 members, with typical-year prices.

| | A grid | B neighbours | C battery 5 kWh | B+C, 10 kWh | REF CEP9 real terms |
|---|---|---|---|---|---|
| Capex, legal / wired | €55,575 | €56,075 / €85,389 | €58,525 | €61,975 / €91,289 | €56,075 |
| Year 1: own use + guests + grid | 5,295 + 0 + 1,338 | 5,295 + 2,487 + 41 | 5,489 + 0 + 1,162 | 5,360 + 2,487 + 27 | 2,025 + 0 + 265 |
| Lost to the compensation cap, year 1 | €394 | €0 | €412 | €0 | €0 |
| **NPV, legal, manager fee €25 per member** | €19,764 | **€23,276** | €12,880 | €13,142 | −€51,122 |
| **NPV, legal, no manager fee (CEP9's real case)** | €19,764 | **€35,256** | €12,880 | €25,122 | −€39,142 |
| **NPV, wired** | **€19,764** | €5,942 | €12,880 | −€4,192 | −€51,122 |

- **Legal, fee €25:** "Recommended: share with 4 neighbouring buildings (33 guests) through the legal route. Payback 9.1 years, NPV EUR 23,276, ROI 146% over 25 years. A battery pays only below EUR 69/kWh installed. Wires pay only if the guests are within 57 m of cable in total."
- **Legal, no fee:** "Recommended: share with 4 neighbouring buildings (33 guests) through the legal route. Payback 8.0 years, NPV EUR 35,256, ROI 184% over 25 years." (the same two break-evens)
- **Wired:** "Recommended: sell the surplus to the grid. Payback 9.5 years, NPV EUR 19,764, ROI 136% over 25 years." The 4 connection kits (one per building) cost €6,000. The default 136 m of cable (€23,814) is only Can Felipa's 105 m × 1.3, because the other three members are listed at the host's own position. **Wired break-even: 57 m of cable in total**, so wires beat selling to the grid only if all four buildings can be reached with less than 57 m of trench.
- **What moves the answer most:**
  - Legal, fee €25: the manager fee FLIPS it (at €50 per member A wins), and so does the compensation price (at €0.10 per kWh A wins); then price change per year.
  - Legal, no fee: only the manager fee flips it, if it went up to €50. Then the battery price and the discount rate.
  - Wired: battery price, discount rate, compensation price; none flips it.
- **CEP9's real terms (REF):** the owner gets only the host's 30% share, and gives the other 70% away. So from the owner's money alone it never pays back (NPV −€39,142 with no manager fee). The value goes to the members: in step 07's `agreed_shares` they save about €5,370 a year together, about €74 a year per home (€94 with taxes).

**Flag: surplus under CEP9's real split.** With the fixed split, **7,129 of 69,508 kWh (10.3%) goes to the grid**, just above the ~10% we treat as "not much". The host alone sends 4,409 kWh of its 20,852 kWh share. CEP9 says "there isn't much production going into surplus" [CEP9, 27 Nov 2026], so **our demand estimates are probably too low**, the host's above all. They are averages of building types, not meters. Real meter data would raise own use and lower the surplus. With our hourly sharing (option B) only 940 kWh (1.4%) goes to the grid.

**Extra case, "what if the school next door joined"** (Institut + Escola Pere IV, 540 W "best blocks", 65.88 kWp, 89,284 kWh a year; folders `data\host\cep9_both`, `data\roi\cep9_both_legal`, `data\roi\cep9_both_wired`):
- Legal: B wins, NPV €36,231.
- Wired: A wins, NPV €24,415, against €18,897 for B wired.
- Wired break-even: 105 m of cable.

## The older tool: `investment.py`

`investment.py` gives a yearly net value and simple payback per scenario. It has a central, low and high panel cost, and the guest-price slider formula `owner_total_at_discount` that the website uses. It has no discounting, no replacements and no compensation cap, so use `roi.py` for decisions.

```powershell
.venv\Scripts\python.exe -m step08_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp 65.88 --out data\investment\cep9
```

Its prices are in `CASES` at the top of `investment.py`, with sources in SOURCES.md. Its battery price now also comes from `costs.csv`.

**The guest-price slider:** guests pay (1 − discount) × the grid price of each hour, 10% by default. `owner_total_at_discount(result, discount)` recomputes the owner's money without re-running anything. The battery's choices hardly depend on the discount.
