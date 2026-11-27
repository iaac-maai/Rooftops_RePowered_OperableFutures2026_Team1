"""Step 08 roi.py: offline checks on a small made-up case (no files from earlier steps, no internet)."""
import csv
import json

import numpy as np
import pytest

from step06_prices_and_battery import battery_types as bt
from step06_prices_and_battery import dispatch
from step08_compare_investment import roi
from step08_compare_investment.costs import COSTS_CSV, STATUSES, load_costs, values

SUMMER = np.array([0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0], bool)   # Jun, Jul, Aug


def _monthly(export, grid_eur):
    export = np.asarray(export, float)
    return {"export_kwh": export.tolist(), "export_spot_eur": (export * 0.05).tolist(),
            "host_grid_kwh": (np.asarray(grid_eur) / 0.15).tolist(), "host_grid_eur": list(map(float, grid_eur))}


def _case():
    """10 kWp host: lots of surplus in summer, when (like a school in August) it buys little from the grid."""
    grid_eur = np.where(SUMMER, 5.0, 80.0)
    a = {"battery_kwh": 0.0, "cycles_per_year": 0.0, "host_saving_eur": 1000.0, "guest_sales_eur": 0.0,
         "monthly": _monthly(np.where(SUMMER, 900.0, 300.0), grid_eur)}
    c_rows = [a,
              {"battery_kwh": 10.0, "cycles_per_year": 250.0, "host_saving_eur": 1150.0, "guest_sales_eur": 0.0,
               "monthly": _monthly(np.where(SUMMER, 780.0, 180.0), grid_eur * 0.8)},
              {"battery_kwh": 20.0, "cycles_per_year": 200.0, "host_saving_eur": 1250.0, "guest_sales_eur": 0.0,
               "monthly": _monthly(np.where(SUMMER, 700.0, 100.0), grid_eur * 0.7)}]
    b = {"battery_kwh": 0.0, "cycles_per_year": 0.0, "host_saving_eur": 1000.0, "guest_sales_eur": 700.0,
         "monthly": _monthly(np.where(SUMMER, 300.0, 50.0), grid_eur)}
    guests = [{"id": "office_1", "use_type": "office", "distance_m": 60.0, "count": 1},
              {"id": "homes_3", "use_type": "home", "distance_m": 0.0, "count": 3}]
    return {"kwp": 10.0, "price_year": "typical", "battery_type": "lfp", "A": a, "C_rows": c_rows, "B": b,
            "BC_rows": [], "guests": guests, "guest_discount": 0.10, "host_generation_kwh": 14000,
            "host_self_consumed_kwh": 7000, "host_surplus_kwh": 7000}


@pytest.fixture
def costs():
    return load_costs()


def test_costs_csv_every_number_has_a_source_or_is_an_assumption():
    with open(COSTS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ["key", "value", "unit", "low", "high", "source", "status"]
    for r in rows:
        assert r["status"] in STATUSES, r["key"]
        assert float(r["value"]) == float(r["value"])                 # a number
        if r["status"] == "sourced":
            assert r["source"].strip(), f"{r['key']} says sourced but names no source"
        if r["low"] and r["high"]:
            assert float(r["low"]) <= float(r["value"]) <= float(r["high"]), r["key"]


def test_battery_price_comes_from_costs_csv(costs):
    assert bt.LFP_CAPEX_EUR_PER_KWH == costs["battery_installed_eur_per_kwh"]["value"]
    assert bt.get("lfp")["capex_eur_per_kwh"] == bt.LFP_CAPEX_EUR_PER_KWH


def test_cap_never_pays_more_than_the_months_grid_energy(costs):
    c = values(costs)
    m = _case()["A"]["monthly"]
    g = roi.grid_income(m, 10.0, c)
    assert all(p <= cap + 1e-9 for p, cap in zip(g["by_month_eur"], m["host_grid_eur"]))
    raw = np.array(m["export_kwh"]) * c["grid_compensation_eur_per_kwh"]
    assert g["income_eur"] + g["lost_to_cap_eur"] == pytest.approx(raw.sum())
    assert g["lost_to_cap_eur"] > 0                     # summer: lots of export, small bill
    big = roi.grid_income(m, 150.0, c)                  # over 100 kW: market price, no cap
    assert big["lost_to_cap_eur"] == 0 and big["income_eur"] == pytest.approx(sum(m["export_spot_eur"]))


def test_npv_with_no_discounting_is_the_plain_sum(costs):
    c = {**values(costs), "discount_rate": 0.0}
    o = roi.build_option("A", _case()["A"], 10.0, c)
    assert o["npv_eur"] == pytest.approx(sum(o["cash_in"]) - sum(o["cash_out"]) - o["capex_eur"])
    assert o["roi_lifetime"] == pytest.approx(o["npv_eur"] / o["capex_eur"])
    assert len(o["cumulative_cash"]) == int(c["analysis_years"]) + 1


def test_option_a_has_no_extra_capex(costs):
    c = values(costs)
    o = roi.evaluate(_case(), c, "legal", 0.0)
    assert o["A"]["capex_parts"]["option_eur"] == 0
    assert o["A"]["capex_eur"] == pytest.approx(10.0 * c["panel_capex_eur_per_kwp"])
    assert o["B"]["capex_eur"] > o["A"]["capex_eur"] and o["C"]["capex_eur"] > o["A"]["capex_eur"]


def test_inverter_and_battery_replacements(costs):
    c = values(costs)
    b = roi.battery_terms(10.0, 250.0, 590.0, c)          # 2,400 cycles / 250 a year = 9.6 years -> every 9 years
    assert b["life_years"] == pytest.approx(9.6)
    assert [y for y, _ in b["replacements"]] == [9, 18]
    o = roi.build_option("A", _case()["A"], 10.0, c)
    inv_year = int(c["inverter_replacement_year"])
    assert o["cash_out"][inv_year - 1] - o["cash_out"][0] == pytest.approx(10.0 * c["inverter_replacement_eur_per_kwp"])


def test_battery_break_even_price_makes_c_equal_a(costs):
    c = values(costs)
    case = _case()
    be = roi.battery_break_even(case, c)
    assert be is not None and 0 < be < roi.BATTERY_PRICE_MAX
    at = roi.evaluate(case, {**c, "battery_installed_eur_per_kwh": be}, "legal", 0.0)
    assert at["C"]["npv_eur"] == pytest.approx(at["A"]["npv_eur"], abs=0.5)


def test_max_cable_times_cost_per_metre_is_the_npv_gap(costs):
    c = values(costs)
    case = _case()
    m = roi.max_cable_m(case, c)
    o = roi.evaluate(case, c, "wired", 0.0)
    per_m = c["cable_buried_eur_per_m"] + c["trench_and_repave_eur_per_m"]
    assert m * per_m == pytest.approx(o["B"]["npv_eur"] - o["A"]["npv_eur"])
    at_limit = roi.evaluate(case, c, "wired", m)          # with exactly that much cable, B ties with A
    assert at_limit["B"]["npv_eur"] == pytest.approx(o["A"]["npv_eur"])


def test_connection_costs_count_dwellings(costs):
    c = values(costs)
    guests = _case()["guests"]                            # 1 office + 3 homes = 4 guests
    w = roi.connection_terms("wired", guests, c, 100.0)
    assert w["capex_eur"] == pytest.approx(100 * (c["cable_buried_eur_per_m"] + c["trench_and_repave_eur_per_m"])
                                           + 4 * c["guest_connection_kit_eur"])
    lg = roi.connection_terms("legal", guests, c, 100.0)
    assert lg["capex_eur"] == c["legal_net_meter_eur"]
    assert lg["yearly_eur"] == pytest.approx(5 * c["legal_manager_eur_per_member_yr"])   # host + 4 guests


def test_discounted_payback_is_none_when_npv_is_negative(costs):
    c = {**values(costs), "panel_capex_eur_per_kwp": 10000.0}
    o = roi.build_option("A", _case()["A"], 10.0, c)
    assert o["npv_eur"] < 0 and o["discounted_payback_y"] is None
    ok = roi.build_option("A", _case()["A"], 10.0, values(costs))
    assert ok["npv_eur"] > 0 and ok["discounted_payback_y"] is not None
    assert ok["cumulative_cash"][ok["discounted_payback_y"]] >= 0
    assert ok["cumulative_cash"][ok["discounted_payback_y"] - 1] < 0


def test_run_writes_summary_cashflows_and_chart(costs, tmp_path):
    s = roi.run(_case(), costs, "legal")
    assert s["recommended"] in s["options"] and s["recommendation"].startswith(("Recommended", "Least bad"))
    assert len(s["most_sensitive"]) == 3
    assert all(r["low"] is not None and r["high"] is not None for r in s["sensitivity"])
    roi.write_outputs(s, tmp_path)
    saved = json.loads((tmp_path / "roi_summary.json").read_text(encoding="utf-8"))
    assert set(saved["options"]) == {"A", "B", "C"}
    with open(tmp_path / "roi_cashflows.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3 * (int(values(costs)["analysis_years"]) + 1)
    assert (tmp_path / "roi_line.png").stat().st_size > 0

    from step09_publish_report.export_site_data import roi_block
    block = roi_block(saved)
    a = block["options"]["A"]
    assert len(a["cash_in"]) == len(a["cash_out"]) == int(values(costs)["analysis_years"])
    assert block["costs"]["battery_installed_eur_per_kwh"]["status"] == "sourced"


def test_dispatch_monthly_figures_add_up():
    gen = np.tile(np.r_[np.zeros(8), np.full(8, 50.0), np.zeros(8)], 2)
    demand = np.vstack([np.full(48, 10.0), np.full(48, 5.0)])
    price, spot = np.full(48, 0.15), np.full(48, 0.05)
    months = np.r_[np.full(24, 6), np.full(24, 7)]
    b = {**bt.get("lfp"), "kwh": 10.0}
    f = dispatch.simulate_year(gen, demand, price, spot, b)
    a = dispatch.account(f, gen, demand, price, spot, 0.10, ["host", "g"], b, months)
    m = a["monthly"]
    assert sum(m["export_kwh"]) == pytest.approx(a["exported_kwh"], abs=1)
    host_bought = a["per_building"]["host"]["use_kwh"] - a["per_building"]["host"]["from_roof_kwh"]
    assert sum(m["host_grid_kwh"]) == pytest.approx(host_bought, abs=1)
    assert m["export_kwh"][0] == 0 and m["host_grid_eur"][5] > 0
