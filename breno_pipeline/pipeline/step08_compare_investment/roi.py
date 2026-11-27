"""Step 08: the roof owner's return over 25 years, for three ways of using the surplus.

    python -m step08_compare_investment.roi --host-dir data\\host\\cep9 --battery-dir data\\battery\\cep9 ^
        --match-dir data\\match\\cep9_wired --sharing-dir data\\sharing\\cep9 --agreed-dir data\\agreed\\cep9 ^
        --prices-dir data\\prices --kwp 52.38 --connection legal --out data\\roi\\cep9_legal
    add --manager-fee-eur-per-member 0 for CEP9's real case (no manager fee)

The owner pays for the panels and keeps them. The host uses what it can (the same in every option).
The options differ only in what happens to the SURPLUS, the solar the host doesn't use itself:

  A    sell it to the grid
  B    share it with a community of neighbours: guests pay (1 - discount) x PVPC of each hour
       (default discount 10%); what they don't take goes to the grid as in A
  C    a battery at the host, charged only from the panels; what is left goes to the grid as in A
  B+C  both: neighbours and a battery
  REF  "CEP9 real terms", for reference only (never recommended): fixed shares agreed in advance
       (step 07 agreed_shares.py, e.g. host 0.30), the power given to the members for free. The owner
       gets only the host's own share x PVPC, plus compensation for the part of that share the host
       doesn't use. Legal-route costs apply.

All options use the same panels. Nothing is simulated here: the kWh and EUR come from the files
the earlier steps wrote.
  A    step 04 host_table.csv: self-consumed and surplus kWh per hour, priced with step 06's PVPC
  B    step 07 battery_agent_summary.json, "without_battery" (guests, no battery)
  C    step 06 battery_sizing.json, one row per battery size
  B+C  step 07 battery_agent_summary.json, "sizing_with_guests" (guests, one row per battery size)
  REF  step 07 agreed_shares_summary.json (in --agreed-dir): the host's share and the members;
       the host's hourly kWh are worked out from host_table.csv x that share
  guests and distances: step 07 shortlist.csv (in --match-dir)

MONEY IN, YEAR 1
  own use        = kWh the host gets from the roof x PVPC of that hour (C and B+C: includes the battery)
  guest sales    = what the guests pay (B and B+C only)
  grid income    = up to 100 kW (simplified compensation): each month,
                     min(exported kWh x grid_compensation_eur_per_kwh, EUR of grid energy the host still bought)
                   The rest is lost: no cash, and it can't be taken off taxes or grid fees.
                   Over 100 kW: exported kWh x OMIE price of each hour, no cap.

CASH FLOW, YEAR t = 1 .. analysis_years
  cash_in_t  = money in, year 1 x (1 - degradation)^(t-1) x (1 + escalation)^(t-1)
  cash_out_t = panel upkeep + the option's yearly costs + replacements due that year
  year 0     = -(panel capex + the option's capex)

METRICS
  NPV                  = sum over t of (cash_in_t - cash_out_t) / (1 + r)^t - capex
  ROI over the life    = (sum cash_in - sum cash_out - capex) / capex      (NOT discounted)
  simple payback       = capex / (year-1 cash_in - year-1 cash_out)
  discounted payback   = first year from which the discounted running total stays at or above 0
                         (None if the NPV is below 0)

Every cost comes from step08_compare_investment/costs.csv (value, low, high, source, status).
The choices made in this file (all ASSUMPTIONS, also listed in the README):
  - ROUTE_FACTOR 1.3: a cable is 1.3 x the straight-line distance (streets aren't straight)
  - wired: one connection kit per guest BUILDING (30 homes in one block = 1 kit).
  - legal: the manager fee is per member (supply point): a "home" candidate with N dwellings is N
    members, any other building 1; members = host + guests.
  - REF: the members' unused shares are compensated on their own bills, not the owner's.
  - the cap compares the compensation with the host's grid kWh x the WHOLE PVPC price. The real
    rule caps it at the energy part of the bill only, so our cap is a bit generous.
  - the cap is applied to the host's bill only (with guests too).
  - the legal route uses the same hourly kWh as the wired one (hourly sharing coefficients);
    only the costs differ.
  - a battery is replaced every floor(life) years at today's price; nothing is left over at the end
    of the analysis (no residual value), and no replacement is bought in the last year.
  - upkeep and other costs don't rise with prices; only money in is escalated.

Outputs in --out: roi_summary.json, roi_cashflows.csv, roi_line.png.
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table
from step05_forecast_demand.baseline_profiles import local_hours
from step06_prices_and_battery import battery_types as bt
from step06_prices_and_battery.prices import read_solar_year_prices
from step08_compare_investment.costs import COSTS_CSV, load_costs, values

ROUTE_FACTOR = 1.3          # ASSUMPTION: cable route length / straight-line distance
OPTIONS = ("A", "B", "C", "B+C", "REF")
REFERENCE = ("REF",)        # shown next to the options, never recommended
BATTERY_PRICE_MAX = 5000.0  # EUR/kWh: the break-even search looks between 0 and this


# ---------------------------------------------------------------- inputs from earlier steps
def _monthly_from_hours(months, export_kwh, export_spot, grid_kwh, grid_pvpc):
    out = {"export_kwh": [], "export_spot_eur": [], "host_grid_kwh": [], "host_grid_eur": []}
    for m in range(1, 13):
        k = months == m
        out["export_kwh"].append(float(export_kwh[k].sum()))
        out["export_spot_eur"].append(float((export_kwh[k] * export_spot[k]).sum()))
        out["host_grid_kwh"].append(float(grid_kwh[k].sum()))
        out["host_grid_eur"].append(float((grid_kwh[k] * grid_pvpc[k]).sum()))
    return out


def _need_monthly(row, where):
    if "monthly" not in row:
        raise SystemExit(f"{where} has no monthly figures: it was written by an older version. "
                         f"Run step 06 battery_size and step 07 battery_agent again.")
    return row["monthly"]


def _money_row(r, where):
    return {"battery_kwh": float(r.get("battery_kwh", 0.0)),
            "cycles_per_year": float(r.get("cycles_per_year", r.get("battery_cycles_per_year", 0.0))),
            "host_saving_eur": float(r["owner_host_saving_eur"]),
            "guest_sales_eur": float(r.get("owner_sales_to_guests_eur", 0.0)),
            "monthly": _need_monthly(r, where)}


def read_guests(match_dir, ids):
    """Step 07's shortlist.csv -> [{id, use_type, distance_m, count}] for the buildings in ids."""
    path = Path(match_dir) / "shortlist.csv"
    rows = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            rows = {r["building_id"]: r for r in csv.DictReader(f)}
    out = []
    for i in ids:
        r = rows.get(i, {})
        dwellings = r.get("dwellings") or ""
        homes = r.get("use_type") == "home" and dwellings not in ("", "None")
        out.append({"id": i, "use_type": r.get("use_type"),
                    "location_private": str(r.get("location_private") or "").lower() in ("yes", "true", "1"),
                    "distance_m": float(r["distance_m"]) if r.get("distance_m") not in (None, "", "None") else None,
                    "count": int(float(dwellings)) if homes else 1})
    return out


def reference_money(gen, demand, host_share, months, pvpc, spot):
    """REF: the host gets host_share x every hour's output; it uses what it needs, the rest of its share
    goes to the grid (compensated on its bill); the other members' shares are free, so no money for them."""
    alloc = host_share * gen
    used = np.minimum(alloc, demand)
    return {"battery_kwh": 0.0, "cycles_per_year": 0.0, "host_saving_eur": float((used * pvpc).sum()),
            "guest_sales_eur": 0.0, "monthly": _monthly_from_hours(months, alloc - used, spot, demand - used, pvpc)}


def read_inputs(host_dir, battery_dir, sharing_dir, match_dir, prices_dir, kwp, price_year="typical",
                battery_type=bt.DEFAULT, agreed_dir=None):
    """Everything roi needs, from the output folders of steps 04, 06 and 07."""
    host = read_host_table(host_dir)
    sy = read_solar_year_prices(Path(prices_dir) / "prices_hourly_solar_year.csv")
    year = int(price_year) if str(price_year).isdigit() else price_year
    pvpc, spot = sy["pvpc"][year], sy["spot"][year]
    _, _, months = local_hours(host["times"])
    self_used, surplus = host["self_consumed_kwh"], host["surplus_kwh"]
    grid = host["host_demand_kwh"] - self_used
    a = {"battery_kwh": 0.0, "cycles_per_year": 0.0, "host_saving_eur": float((self_used * pvpc).sum()),
         "guest_sales_eur": 0.0, "monthly": _monthly_from_hours(months, surplus, spot, grid, pvpc)}
    inputs = {"kwp": float(kwp), "price_year": str(year), "battery_type": battery_type, "A": a,
              "C_rows": [], "B": None, "BC_rows": [], "guests": [], "guest_discount": None,
              "host_generation_kwh": round(float(host["generation_kwh"].sum())),
              "host_self_consumed_kwh": round(float(self_used.sum())), "host_surplus_kwh": round(float(surplus.sum()))}
    if battery_dir:
        bs = json.loads((Path(battery_dir) / "battery_sizing.json").read_text(encoding="utf-8"))
        if str(bs.get("price_year")) != str(year):
            raise SystemExit(f"battery_sizing.json was run with price year {bs.get('price_year')}, not {year}")
        inputs["C_rows"] = [_money_row(r, "battery_sizing.json") for r in bs["rows"] if r["battery_type"] == battery_type]
    if sharing_dir:
        sh = json.loads((Path(sharing_dir) / "battery_agent_summary.json").read_text(encoding="utf-8"))
        res = sh["price_years"][str(year)]
        inputs["B"] = _money_row(res["without_battery"], "battery_agent_summary.json")
        sizing = sh.get("sizing_with_guests") or []
        if sizing and str(year) == "typical":
            inputs["BC_rows"] = [_money_row(r, "battery_agent_summary.json") for r in sizing
                                 if r["battery_type"] == battery_type]
        else:    # the size was fixed with --battery-kwh, or another price year: only the chosen size is known
            inputs["BC_rows"] = [_money_row({**res["with_battery"], "battery_kwh": sh["battery_kwh"]},
                                            "battery_agent_summary.json")]
        inputs["guests"] = read_guests(match_dir or sharing_dir, sh["buildings"][1:])
        inputs["guest_discount"] = sh["guest_discount"]
    if agreed_dir:
        ag = json.loads((Path(agreed_dir) / "agreed_shares_summary.json").read_text(encoding="utf-8"))
        per = ag["per_building"]
        share = float(per["host"]["share"])
        inputs["REF"] = reference_money(host["generation_kwh"], host["host_demand_kwh"], share, months, pvpc, spot)
        inputs["REF_terms"] = {"host_share": share, "shares": {k: v["share"] for k, v in per.items()},
                               "guest_price_share_of_grid": ag.get("guest_price_share_of_grid", 0.0),
                               "members": [{"id": k, "count": int(v.get("dwellings") or 1)} for k, v in per.items()
                                           if k != "host"]}
    return inputs


# ---------------------------------------------------------------- the money
def grid_income(monthly, kwp, c):
    """Money for the exported kWh in year 1. Up to simplified_compensation_max_kw: compensation with the
    monthly cap; above it: the OMIE price of each hour, no cap."""
    exported = np.asarray(monthly["export_kwh"], float)
    if kwp > c["simplified_compensation_max_kw"]:
        paid = np.asarray(monthly["export_spot_eur"], float)
        return {"rule": "market (OMIE), no cap", "income_eur": float(paid.sum()), "uncapped_eur": float(paid.sum()),
                "lost_to_cap_eur": 0.0, "by_month_eur": paid.round(2).tolist(),
                "exported_kwh": float(exported.sum())}
    raw = exported * c["grid_compensation_eur_per_kwh"]
    cap = np.asarray(monthly["host_grid_eur"], float)
    paid = np.minimum(raw, cap)
    return {"rule": "simplified compensation, monthly cap", "income_eur": float(paid.sum()),
            "uncapped_eur": float(raw.sum()), "lost_to_cap_eur": float((raw - paid).sum()),
            "by_month_eur": paid.round(2).tolist(), "lost_by_month_eur": (raw - paid).round(2).tolist(),
            "exported_kwh": float(exported.sum())}


def growth(t, c):
    """Money-in factor for year t (1 = year 1): panel degradation and price escalation."""
    return (1 - c["panel_degradation_per_yr"]) ** (t - 1) * (1 + c["price_escalation_per_yr"]) ** (t - 1)


def cash_flows(year1_in, capex, yearly_out, replacements, c):
    """-> rows for years 0..N: year, cash_in, cash_out, net, cumulative_discounted.
    replacements = [(year, EUR), ...]; only years 1..N count."""
    n, r = int(c["analysis_years"]), c["discount_rate"]
    rows = [{"year": 0, "cash_in": 0.0, "cash_out": capex, "replacements": 0.0, "net": -capex,
             "cumulative_discounted": -capex}]
    cum = -capex
    for t in range(1, n + 1):
        rep = sum(eur for y, eur in replacements if y == t)
        cin = year1_in * growth(t, c)
        cout = yearly_out + rep
        cum += (cin - cout) / (1 + r) ** t
        rows.append({"year": t, "cash_in": cin, "cash_out": cout, "replacements": rep, "net": cin - cout,
                     "cumulative_discounted": cum})
    return rows


def metrics(rows, capex):
    years = rows[1:]
    npv = rows[-1]["cumulative_discounted"]
    total_in = sum(r["cash_in"] for r in years)
    total_out = sum(r["cash_out"] for r in years)
    net1 = years[0]["net"]
    disc = None
    if npv >= 0:
        cum = [r["cumulative_discounted"] for r in rows]
        below = [k for k, v in enumerate(cum) if v < 0]
        disc = (below[-1] + 1) if below else 0
    return {"npv_eur": npv, "roi_lifetime": (total_in - total_out - capex) / capex if capex else None,
            "simple_payback_y": capex / net1 if net1 > 0 else None, "discounted_payback_y": disc,
            "lifetime_cash_in_eur": total_in, "lifetime_cash_out_eur": total_out}


def battery_terms(kwh, cycles, price, c, battery_type=bt.DEFAULT):
    """Capex, yearly upkeep, replacements and life of a battery of kwh at an installed price per kWh."""
    if kwh <= 0:
        return {"capex_eur": 0.0, "yearly_eur": 0.0, "replacements": [], "life_years": None}
    b = {**bt.get(battery_type), "kwh": kwh}
    capex = kwh * price
    life = bt.life_years(b, cycles)
    every = max(1, math.floor(life))
    n = int(c["analysis_years"])
    return {"capex_eur": capex, "yearly_eur": c["battery_om_share_of_capex_yr"] * capex,
            "replacements": [(t, capex) for t in range(every, n, every)], "life_years": life}


def connection_terms(connection, guests, c, cable_m):
    """Extra capex and yearly cost of linking the guests: a cable (wired) or the legal route (no cable)."""
    if connection == "wired":
        # one connection kit per guest BUILDING (a block of 30 homes is one building, one kit)
        buildings = len(guests)
        per_m = c["cable_buried_eur_per_m"] + c["trench_and_repave_eur_per_m"]
        return {"capex_eur": cable_m * per_m + buildings * c["guest_connection_kit_eur"], "yearly_eur": 0.0,
                "parts": {"cable_m": cable_m, "cable_eur": cable_m * per_m,
                          "kits_eur": buildings * c["guest_connection_kit_eur"], "guest_buildings": buildings}}
    # legal route: the manager fee is per member (supply point): each home signs the sharing agreement
    members = 1 + sum(g["count"] for g in guests)
    return {"capex_eur": c["legal_net_meter_eur"], "yearly_eur": members * c["legal_manager_eur_per_member_yr"],
            "parts": {"net_meter_eur": c["legal_net_meter_eur"], "members": members,
                      "manager_eur_per_year": members * c["legal_manager_eur_per_member_yr"]}}


def build_option(name, money, kwp, c, extra_capex=0.0, extra_yearly=0.0, extra_replacements=(), details=None):
    inc = grid_income(money["monthly"], kwp, c)
    own, sales = money["host_saving_eur"], money["guest_sales_eur"]
    year1_in = own + sales + inc["income_eur"]
    panel_capex = kwp * c["panel_capex_eur_per_kwp"]
    capex = panel_capex + extra_capex
    panel_om = kwp * c["panel_om_eur_per_kwp_yr"]
    reps = [(int(c["inverter_replacement_year"]), kwp * c["inverter_replacement_eur_per_kwp"])] + list(extra_replacements)
    rows = cash_flows(year1_in, capex, panel_om + extra_yearly, reps, c)
    m = metrics(rows, capex)
    g = sum(growth(t, c) for t in range(1, int(c["analysis_years"]) + 1))
    n = int(c["analysis_years"])
    replacements_total = sum(r["replacements"] for r in rows[1:])
    return {"option": name, **(details or {}), **m,
            "capex_eur": capex, "capex_parts": {"panels_eur": panel_capex, "option_eur": extra_capex},
            "year1": {"own_use_eur": own, "guest_sales_eur": sales, "grid_income_eur": inc["income_eur"],
                      "upkeep_eur": panel_om + extra_yearly},
            "grid": inc,
            "money_breakdown": {"own_use_eur": own * g, "guest_sales_eur": sales * g, "grid_income_eur": inc["income_eur"] * g,
                                "upkeep_eur": -(panel_om + extra_yearly) * n, "replacements_eur": -replacements_total,
                                "capex_eur": -capex},
            "cash_in": [r["cash_in"] for r in rows[1:]], "cash_out": [r["cash_out"] for r in rows[1:]],
            "cumulative_cash": [r["cumulative_discounted"] for r in rows], "rows": rows}


def best_battery(name, rows, kwp, c, price, battery_type, extra_capex=0.0, extra_yearly=0.0, details=None):
    """The battery size (> 0 kWh) with the highest NPV, among the sizes step 06 / 07 ran."""
    best = None
    for r in rows:
        if r["battery_kwh"] <= 0:
            continue
        b = battery_terms(r["battery_kwh"], r["cycles_per_year"], price, c, battery_type)
        o = build_option(name, r, kwp, c, extra_capex + b["capex_eur"], extra_yearly + b["yearly_eur"], b["replacements"],
                         {**(details or {}), "battery_kwh": r["battery_kwh"], "battery_capex_eur": b["capex_eur"],
                          "battery_life_years": b["life_years"], "battery_cycles_per_year": r["cycles_per_year"]})
        if best is None or o["npv_eur"] > best["npv_eur"]:
            best = o
    return best


def evaluate(inputs, c, connection="legal", cable_m=0.0):
    """All options for one set of cost values c ({key: value}). -> {option: result} (B, C, B+C may be missing)."""
    kwp, price, bt_type = inputs["kwp"], c["battery_installed_eur_per_kwh"], inputs["battery_type"]
    out = {"A": build_option("A", inputs["A"], kwp, c)}
    if inputs["C_rows"]:
        out["C"] = best_battery("C", inputs["C_rows"], kwp, c, price, bt_type)
    if inputs["B"] is not None and inputs["guests"]:
        conn = connection_terms(connection, inputs["guests"], c, cable_m)
        det = {"connection": connection, "connection_parts": conn["parts"], "guests": len(inputs["guests"])}
        out["B"] = build_option("B", inputs["B"], kwp, c, conn["capex_eur"], conn["yearly_eur"], details=det)
        if inputs["BC_rows"]:
            out["B+C"] = best_battery("B+C", inputs["BC_rows"], kwp, c, price, bt_type, conn["capex_eur"],
                                      conn["yearly_eur"], det)
    if inputs.get("REF"):            # CEP9's real terms: legal route, fixed shares, power given free
        terms = inputs["REF_terms"]
        conn = connection_terms("legal", terms["members"], c, 0.0)
        out["REF"] = build_option("REF", inputs["REF"], kwp, c, conn["capex_eur"], conn["yearly_eur"],
                                  details={"connection": "legal", "connection_parts": conn["parts"],
                                           "reference": True, "label": "CEP9 real terms", **terms})
    return {k: out[k] for k in OPTIONS if out.get(k) is not None}


def recommended(options):
    """The option with the highest NPV; reference rows (REF) are never recommended."""
    return max((k for k in options if k not in REFERENCE), key=lambda k: options[k]["npv_eur"])


def battery_break_even(inputs, c):
    """Installed EUR/kWh at which the best battery (C) has the same NPV as A. None: never (even free)."""
    if not inputs["C_rows"]:
        return None
    npv_a = build_option("A", inputs["A"], inputs["kwp"], c)["npv_eur"]

    def gap(price):
        return best_battery("C", inputs["C_rows"], inputs["kwp"], c, price, inputs["battery_type"])["npv_eur"] - npv_a

    if gap(0.0) < 0:
        return None
    if gap(BATTERY_PRICE_MAX) > 0:
        return BATTERY_PRICE_MAX
    lo, hi = 0.0, BATTERY_PRICE_MAX
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if gap(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def max_cable_m(inputs, c):
    """Most metres of cable (in total) for which B, wired, still beats A. <= 0: wired never beats A."""
    if inputs["B"] is None or not inputs["guests"]:
        return None
    npv_a = build_option("A", inputs["A"], inputs["kwp"], c)["npv_eur"]
    b0 = evaluate({**inputs, "C_rows": [], "BC_rows": []}, c, "wired", 0.0)["B"]["npv_eur"]
    return (b0 - npv_a) / (c["cable_buried_eur_per_m"] + c["trench_and_repave_eur_per_m"])


def describe(name, o, inputs):
    n_b = len(inputs["guests"])
    n_g = sum(g["count"] for g in inputs["guests"])
    who = f"{n_b} neighbours" if n_g == n_b else f"{n_b} neighbouring buildings ({n_g} guests)"
    route = "through the legal route" if o.get("connection") == "legal" else "with a cable to each"
    text = {"A": "sell the surplus to the grid",
            "B": f"share with {who} {route}",
            "C": f"add a {o.get('battery_kwh', 0):g} kWh battery and sell the rest to the grid",
            "B+C": f"share with {who} {route} and add a {o.get('battery_kwh', 0):g} kWh battery"}
    return text[name]


def sentence(options, rec, inputs, c, break_even, cable):
    o = options[rec]
    n = int(c["analysis_years"])
    pay = f"payback {o['simple_payback_y']:.1f} years" if o["simple_payback_y"] else "it never pays back"
    head = "Recommended" if o["npv_eur"] >= 0 else "Least bad (no option pays back)"
    s = (f"{head}: {describe(rec, o, inputs)}. {pay[0].upper() + pay[1:]}, NPV EUR {o['npv_eur']:,.0f}, "
         f"ROI {o['roi_lifetime']:.0%} over {n} years.")
    if inputs["C_rows"]:
        s += (" A battery doesn't pay even if it were free." if break_even is None else
              f" A battery pays only below EUR {break_even:,.0f}/kWh installed.")
    if cable is not None:
        s += (" Wires never beat selling to the grid." if cable <= 0 else
              f" Wires pay only if the guests are within {cable:,.0f} m of cable in total.")
    return s


def sensitivity(inputs, costs, connection, cable_m, base_rec):
    """Re-run every option with the low and the high value of each cost that has them.
    margin = NPV of the base recommendation - the best NPV of the others (below 0: the recommendation flips)."""
    base = values(costs)
    rows = []
    for key, row in costs.items():
        if row["low"] is None or row["high"] is None:
            continue
        r = {"key": key, "low": row["low"], "high": row["high"], "status": row["status"]}
        for side in ("low", "high"):
            opts = evaluate(inputs, {**base, key: row[side]}, connection, cable_m)
            others = [v["npv_eur"] for k, v in opts.items() if k != base_rec and k not in REFERENCE]
            r[f"npv_{side}"] = {k: round(v["npv_eur"]) for k, v in opts.items()}
            r[f"recommended_{side}"] = recommended(opts)
            r[f"margin_{side}"] = round(opts[base_rec]["npv_eur"] - max(others)) if others else None
        r["swing_eur"] = abs((r["margin_high"] or 0) - (r["margin_low"] or 0))
        r["flips"] = base_rec not in (r["recommended_low"], r["recommended_high"]) or \
            r["recommended_low"] != r["recommended_high"]
        rows.append(r)
    rows.sort(key=lambda r: (-int(r["flips"]), -r["swing_eur"]))
    return rows


def run(inputs, costs, connection="legal", cable_m=None):
    """The whole analysis -> summary dict (what roi_summary.json holds)."""
    c = values(costs)
    warnings = []
    dist = [g["distance_m"] for g in inputs["guests"]]
    if cable_m is None:
        cable_m = ROUTE_FACTOR * sum(d or 0.0 for d in dist)
        cable_source = f"sum of the guests' straight-line distances x {ROUTE_FACTOR} (ASSUMPTION)"
        at_host = [g["id"] + (" (location private)" if g.get("location_private") else "")
                   for g in inputs["guests"] if not g["distance_m"]]
        if at_host and connection == "wired":
            warnings.append(f"{len(at_host)} of {len(inputs['guests'])} guests ({', '.join(at_host)}) have no known "
                            f"distance and count as 0 m, so their cable costs nothing here. Give --cable-m with a real "
                            f"length; max_cable_m shows how much cable the wired option can afford.")
    else:
        cable_source = "--cable-m"
    if inputs["kwp"] <= c["simplified_compensation_max_kw"]:
        warnings.append(f"{inputs['kwp']:g} kWp is at most {c['simplified_compensation_max_kw']:g} kW: exports earn "
                        f"compensation, capped each month at the host's grid energy bill.")
    warnings.append("Prices are PVPC for every building; supplies over 15 kW really pay the 3.0TD tariff (step 06).")
    options = evaluate(inputs, c, connection, cable_m)
    rec = recommended(options)
    be = battery_break_even(inputs, c)
    cable = max_cable_m(inputs, c)
    sens = sensitivity(inputs, costs, connection, cable_m, rec)
    return {
        "connection": connection, "kwp": inputs["kwp"], "price_year": inputs["price_year"],
        "guest_discount": inputs["guest_discount"], "guests": inputs["guests"],
        "cable_m": cable_m, "cable_m_source": cable_source,
        "host": {"generation_kwh": inputs["host_generation_kwh"], "self_consumed_kwh": inputs["host_self_consumed_kwh"],
                 "surplus_kwh": inputs["host_surplus_kwh"]},
        "options": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in options.items()},
        "recommended": rec, "recommendation": sentence(options, rec, inputs, c, be, cable),
        "break_even": {"battery_eur_per_kwh": be, "battery_note": "installed price at which NPV(C) = NPV(A); "
                       "None = never, even free", "max_cable_m": cable,
                       "cable_note": "(NPV(B, wired, 0 m of cable) - NPV(A)) / (cable + trench EUR per m); "
                                     "<= 0 = wires never beat selling to the grid"},
        "sensitivity": sens, "most_sensitive": [r["key"] for r in sens[:3]],
        "roi_note": "ROI over the life is NOT discounted; NPV and the discounted payback are.",
        "costs_used": costs, "warnings": warnings,
        "_rows": {k: v["rows"] for k, v in options.items()},
    }


# ---------------------------------------------------------------- outputs
COLOURS = {"A": (90, 90, 90), "B": (31, 119, 180), "C": (214, 120, 20), "B+C": (44, 150, 70), "REF": (148, 103, 189)}


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:          # Pillow before 10.1
        return ImageFont.load_default()


def _wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def draw_line(summary, path):
    """Cumulative discounted cash of each option, year 0..N, zero line, payback markers; title = the sentence."""
    from PIL import Image, ImageDraw
    W, H, left, right, bottom = 1250, 700, 90, 320, 60
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_title, f = _font(17), _font(14)
    title = _wrap(d, summary["recommendation"], f_title, W - 40)
    top = 20 + 22 * len(title) + 20
    for k, line in enumerate(title):
        d.text((20, 15 + 22 * k), line, fill=(20, 20, 20), font=f_title)
    opts = summary["options"]
    n = len(next(iter(opts.values()))["cumulative_cash"]) - 1
    lo = min(min(o["cumulative_cash"]) for o in opts.values())
    hi = max(max(o["cumulative_cash"]) for o in opts.values())
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    pad = 0.05 * (hi - lo or 1.0)
    lo, hi = lo - pad, hi + pad
    x = lambda t: left + (W - left - right) * t / n
    y = lambda v: top + (H - top - bottom) * (hi - v) / (hi - lo)
    step = 10 ** math.floor(math.log10(max(hi - lo, 1.0) / 4))
    step *= next(m for m in (1, 2, 5, 10) if (hi - lo) / (step * m) <= 8)
    v = math.ceil(lo / step) * step
    while v <= hi:
        d.line([(left, y(v)), (W - right, y(v))], fill=(232, 232, 232))
        d.text((8, y(v) - 8), f"{v / 1000:,.0f}k", fill=(90, 90, 90), font=f)
        v += step
    for t in range(0, n + 1, 5):
        d.line([(x(t), top), (x(t), H - bottom)], fill=(240, 240, 240))
        d.text((x(t) - 6, H - bottom + 8), str(t), fill=(90, 90, 90), font=f)
    d.line([(left, y(0)), (W - right, y(0))], fill=(0, 0, 0), width=2)
    d.text((left, H - bottom + 30), "year", fill=(60, 60, 60), font=f)
    d.text((8, top - 18), "EUR, discounted, running total", fill=(60, 60, 60), font=f)
    for k, (name, o) in enumerate(opts.items()):
        col = COLOURS.get(name, (0, 0, 0))
        pts = [(x(t), y(v)) for t, v in enumerate(o["cumulative_cash"])]
        d.line(pts, fill=col, width=4 if name == summary["recommended"] else 2)
        p = o["discounted_payback_y"]
        if p is not None:
            cx, cy = x(p), y(o["cumulative_cash"][p])
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], outline=col, width=3)
        short = {"A": "grid", "B": "neighbours", "C": "battery", "B+C": "both", "REF": "CEP9 real terms"}[name]
        if o.get("battery_kwh"):
            short += f" {o['battery_kwh']:g} kWh"
        label = f"{name} {short}: NPV {o['npv_eur'] / 1000:,.1f}k" + (f", pays in {p} y" if p is not None else ", never pays")
        d.line([(W - right + 10, top + 10 + 24 * k), (W - right + 30, top + 10 + 24 * k)], fill=col, width=4)
        d.text((W - right + 35, top + 2 + 24 * k), label, fill=(30, 30, 30), font=_font(12))
    d.text((W - right + 10, top + 10 + 24 * len(opts)), "o = discounted payback", fill=(90, 90, 90), font=_font(12))
    img.save(path)


def write_outputs(summary, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = summary.pop("_rows")
    with open(out / "roi_cashflows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["option", "year", "cash_in", "cash_out", "net", "cumulative_discounted"])
        for name, rr in rows.items():
            for r in rr:
                w.writerow([name, r["year"], round(r["cash_in"], 2), round(r["cash_out"], 2), round(r["net"], 2),
                            round(r["cumulative_discounted"], 2)])
    (out / "roi_summary.json").write_text(json.dumps(_rounded(summary), indent=2, ensure_ascii=False), encoding="utf-8")
    draw_line(summary, out / "roi_line.png")


def _rounded(x):
    if isinstance(x, float):
        return round(x, 4) if abs(x) < 10 else round(x, 2)
    if isinstance(x, dict):
        return {k: _rounded(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_rounded(v) for v in x]
    return x


def print_table(s):
    print(f"Connection: {s['connection']}, {s['kwp']:g} kWp, prices: {s['price_year']} year, cable {s['cable_m']:,.0f} m")
    print(f"  {'option':6} {'capex':>9} {'own use':>9} {'guests':>8} {'grid':>8} {'lost cap':>9} {'NPV':>10} "
          f"{'ROI*':>6} {'payback':>8} {'disc.pb':>8}  battery")
    for k, o in s["options"].items():
        y1 = o["year1"]
        pb = f"{o['simple_payback_y']:.1f}" if o["simple_payback_y"] else "-"
        dpb = "-" if o["discounted_payback_y"] is None else str(o["discounted_payback_y"])
        bat = f"{o['battery_kwh']:g} kWh" if o.get("battery_kwh") else ""
        print(f"  {k:6} {o['capex_eur']:>9,.0f} {y1['own_use_eur']:>9,.0f} {y1['guest_sales_eur']:>8,.0f} "
              f"{y1['grid_income_eur']:>8,.0f} {o['grid']['lost_to_cap_eur']:>9,.0f} {o['npv_eur']:>10,.0f} "
              f"{o['roi_lifetime']:>6.0%} {pb:>8} {dpb:>8}  {bat}")
    print("  EUR; own use, guests, grid and lost cap are year 1. *ROI over the life, NOT discounted.")
    print("  " + s["recommendation"])
    moves = []
    for r in s["sensitivity"][:3]:
        moves.append(f"{r['key']} (" + ("FLIPS it" if r["flips"] else f"margin swings EUR {r['swing_eur']:,.0f}") + ")")
    print("  Moves the answer most: " + ", ".join(moves))
    for w in s["warnings"]:
        print("  NOTE: " + w)


def main():
    ap = argparse.ArgumentParser(description="Step 08: owner's 25-year return for grid, neighbours and battery")
    ap.add_argument("--host-dir", required=True, help="step 04's output folder (host_table.csv)")
    ap.add_argument("--battery-dir", help="step 06's output folder (battery_sizing.json): option C")
    ap.add_argument("--match-dir", help="step 07 optimise's output folder (shortlist.csv: guests and distances)")
    ap.add_argument("--sharing-dir", help="step 07 battery_agent's output folder: options B and B+C")
    ap.add_argument("--prices-dir", default="data/prices", help="step 06's prices folder")
    ap.add_argument("--price-year", default="typical", help="typical, 2023, 2024 or 2025")
    ap.add_argument("--kwp", type=float, required=True, help="installed kWp (step 03's yield file)")
    ap.add_argument("--connection", choices=("legal", "wired"), default="legal",
                    help="how guests are linked: legal = no cable, a net meter and a yearly manager fee; "
                         "wired = a cable and a connection kit per guest")
    ap.add_argument("--cable-m", type=float, help="total cable length in metres (wired); default: the guests' "
                                                  f"straight-line distances x {ROUTE_FACTOR}")
    ap.add_argument("--manager-fee-eur-per-member", type=float,
                    help="legal route: yearly manager fee per member, replacing costs.csv's "
                         "legal_manager_eur_per_member_yr (CEP9 pays 0: the Barcelona Energy Agency prepares "
                         "the coefficient file)")
    ap.add_argument("--agreed-dir", help="step 07 agreed_shares output folder: adds the reference row "
                                         "'CEP9 real terms' (fixed shares, power given free)")
    ap.add_argument("--battery-type", default=bt.DEFAULT, choices=list(bt.TYPES))
    ap.add_argument("--costs", default=str(COSTS_CSV), help="the costs file (default: step08's costs.csv)")
    ap.add_argument("--out", default="data/roi")
    args = ap.parse_args()
    inputs = read_inputs(args.host_dir, args.battery_dir, args.sharing_dir, args.match_dir, args.prices_dir, args.kwp,
                         args.price_year, args.battery_type, args.agreed_dir)
    costs = load_costs(args.costs)
    overrides = {}
    if args.manager_fee_eur_per_member is not None:
        costs["legal_manager_eur_per_member_yr"] = {**costs["legal_manager_eur_per_member_yr"],
                                                    "value": args.manager_fee_eur_per_member,
                                                    "source": "--manager-fee-eur-per-member (this run)",
                                                    "status": costs["legal_manager_eur_per_member_yr"]["status"]}
        overrides["legal_manager_eur_per_member_yr"] = args.manager_fee_eur_per_member
    summary = run(inputs, costs, args.connection, args.cable_m)
    summary["overrides"] = overrides
    summary["inputs"] = {"host_dir": args.host_dir, "battery_dir": args.battery_dir, "match_dir": args.match_dir,
                         "agreed_dir": args.agreed_dir,
                         "sharing_dir": args.sharing_dir, "prices_dir": args.prices_dir, "costs": args.costs}
    write_outputs(summary, args.out)
    print_table(summary)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
