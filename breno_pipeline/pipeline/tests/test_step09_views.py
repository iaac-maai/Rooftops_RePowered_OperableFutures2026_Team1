"""Step 09 site_views: the website's spare-solar and average-day data (offline, made-up year)."""
import numpy as np
import pytest

from step04_read_host_demand.host_table import summarise, surplus_map
from step07_share_energy.agreed_shares import run as agreed_run
from step09_publish_report import site_views as sv

TIMES = np.arange(np.datetime64("2023-01-01T00:30"), np.datetime64("2024-01-01T00:30"), np.timedelta64(1, "h"))
H = len(TIMES)                                                   # 8760


def _case():
    utc_hour = (TIMES - TIMES.astype("datetime64[D]")).astype("timedelta64[h]").astype(int)
    gen = np.clip(40.0 * np.sin(np.pi * (utc_hour - 5) / 14), 0, None)      # sun 06-19 UTC
    _, _, wday, month = sv.local_parts(TIMES)
    open_ = (wday < 5) & ~np.isin(month, (7, 8))
    host = np.where(open_ & (utc_hour >= 7) & (utc_hour < 16), 25.0, 2.0)
    guests = np.vstack([np.full(H, 3.0), np.where(wday < 5, 6.0, 1.0)])
    return gen, host, guests


def test_view_totals_match_step04_and_agreed_shares():
    gen, host, guests = _case()
    ids = ["host", "g1", "g2"]
    demand = np.vstack([host, guests])
    shares = np.array([0.30, 0.40, 0.30])
    our_grid = np.full(H, 0.5)
    out = sv.spare_views(TIMES, gen, host, ids, demand, shares, our_grid, host_label="the Institut")
    v = out["views"]
    self_used, surplus = surplus_map(gen, host)
    assert v["total"]["total_kwh"] == summarise(TIMES, gen, host, self_used, surplus)["surplus_kwh"]
    ag = agreed_run(gen, ids, demand, shares, np.full(H, 0.15))
    assert v["cep9_grid"]["total_kwh"] == ag["to_grid_kwh"]
    assert v["host_share"]["total_kwh"] == ag["per_building"]["host"]["to_grid_kwh"]
    assert v["our_tool_grid"]["total_kwh"] == round(our_grid.sum())
    dates, hours, _, _ = sv.local_parts(TIMES)
    assert sv.to_grid(dates, hours, gen, 2023).sum() == pytest.approx(gen.sum())   # exact, DST days included
    for key, view in v.items():       # each cell is rounded to 0.01 kWh for the website: within 0.1% of the total
        assert np.sum(view["grid"]) == pytest.approx(view["total_kwh"], rel=1e-3)
        assert len(view["grid"]) == 365 and all(len(r) == 24 for r in view["grid"])
    assert v["host_share"]["label"] == "Institut's 30% share"


def test_grid_is_in_local_time_with_summer_time():
    vals = np.zeros(H)
    jan = np.where(TIMES == np.datetime64("2023-01-10T11:30"))[0][0]
    jul = np.where(TIMES == np.datetime64("2023-07-10T11:30"))[0][0]
    vals[jan], vals[jul] = 5.0, 7.0
    g = sv.to_grid(*sv.local_parts(TIMES)[:2], vals, 2023)
    assert g[9][12] == 5.0           # 11:30 UTC in January = 12:30 CET -> row 12:00 of 10 Jan
    assert g[190][13] == 7.0         # 11:30 UTC in July = 13:30 CEST -> row 13:00 of 10 Jul


def test_day_labels_weekends_and_holidays():
    days = sv.day_labels(2023)
    assert days[0]["day"] == "Sun 1 Jan" and days[0]["weekend"] and days[0]["holiday"] == "Christmas"
    feb18 = next(d for d in days if d["date"] == "2023-02-18")
    assert feb18["day"] == "Sat 18 Feb" and feb18["weekend"] and feb18["holiday"] is None
    assert next(d for d in days if d["date"] == "2023-04-05")["holiday"] == "Easter"
    assert next(d for d in days if d["date"] == "2023-08-15")["holiday"].startswith("Summer")
    assert sum(d["weekend"] for d in days) == 105


def test_season_profiles_use_the_same_months():
    gen, host, _ = _case()
    p = sv.season_profiles(TIMES, host)
    assert set(p) == {"winter", "spring_autumn", "summer"}
    # the made-up host is closed in July-August: its summer weekday is lower than its spring-autumn weekday
    assert max(p["summer"]["weekday"]) < max(p["spring_autumn"]["weekday"])
    assert p["winter"]["weekend"] == pytest.approx([2.0] * 24)


def test_scale_panels_keeps_yield_per_panel():
    from step03_simulate_generation.scale_panels import scale_yield
    y = {"yield": {"panels": 97, "panel_wp": 540, "kwp": 52.38, "yearly_kwh": 69508, "monthly_kwh": [5792.33] * 12,
                   "peak_hour_kw": 41.98}, "variants": [1]}
    s, f = scale_yield(y, 108)
    assert s["yield"]["kwp"] == 58.32 and s["yield"]["panels"] == 108
    assert s["yield"]["yearly_kwh"] / 108 == pytest.approx(69508 / 97, rel=1e-4)
    assert "ASSUMPTION" in s["scaled"]["assumption"] and "variants" not in s
