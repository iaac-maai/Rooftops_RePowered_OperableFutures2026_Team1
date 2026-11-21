"""Offline tests for the neighbour demand baseline (pipeline/demand). Run from pipeline/:
    python -m pytest tests/test_demand.py
"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from demand import baseline, check_bcn, weather
from demand import calendar_bcn as cal


# ---------- calendar ----------

def test_holiday_table_has_16_rows_a_year_and_the_moved_2023_days():
    h = cal.holiday_table()
    assert h.groupby(pd.to_datetime(h["date"]).dt.year).size().to_dict() == {2023: 16, 2024: 16, 2025: 16, 2026: 16}
    days = set(h["date"])
    assert date(2023, 6, 5) in days and date(2023, 5, 29) not in days    # Whit Monday moved (elections)
    assert date(2023, 9, 25) in days and date(2023, 9, 24) not in days    # La Merce moved off a Sunday
    assert date(2026, 5, 25) in days and date(2026, 9, 24) in days


def test_summer_time_starts_and_ends_on_the_last_sundays():
    start, end = cal.summer_time_utc(2024)
    assert str(start) == "2024-03-31 01:00:00+00:00"
    assert str(end) == "2024-10-27 01:00:00+00:00"
    local, offset = cal.to_local(pd.DatetimeIndex(["2024-01-15 12:00", "2024-07-01 10:00"], tz="UTC"))
    assert list(local.hour) == [13, 12] and list(offset) == [1, 2]


def test_day_types():
    local = pd.DatetimeIndex(["2024-12-25 10:00", "2024-01-06 10:00", "2024-01-07 10:00",
                              "2024-01-08 10:00", "2024-01-13 10:00"])
    assert list(cal.day_types(local)) == ["holiday", "holiday", "sunday", "weekday", "saturday"]


def test_a_year_without_holidays_is_an_error_not_a_silent_gap():
    with pytest.raises(ValueError, match="2030"):
        cal.day_types(pd.DatetimeIndex(["2030-03-04 10:00"]))


def test_easter():
    assert cal.easter_sunday(2024) == date(2024, 3, 31)
    assert cal.easter_sunday(2025) == date(2025, 4, 20)
    assert cal.easter_sunday(2026) == date(2026, 4, 5)


# ---------- library and baseline ----------

LIB = baseline.Library.load()
TEMP_2024 = weather.synthetic_barcelona(2024).to_numpy()


def one(kind, **extra):
    row = {"id": "x", "type": kind, "floor_area_m2": 100.0}
    row.update(extra)
    return pd.DataFrame([row])


def test_schedules_are_complete_and_between_0_and_1():
    for kind, days in LIB.schedules.items():
        for d, v in days.items():
            assert len(v) == 24 and v.min() >= 0 and v.max() <= 1, (kind, d)


def test_one_value_per_utc_hour_and_positive():
    hourly, summary = baseline.run(one("office"), 2024, TEMP_2024, LIB)
    assert len(hourly) == 8784 and (hourly["x"] > 0).all()
    assert summary.loc[0, "kwh_year"] > 0


def test_a_holiday_on_a_wednesday_looks_like_a_sunday_for_a_shop():
    hourly, _ = baseline.run(one("shop"), 2024, np.full(8784, 18.0), LIB)   # no AC or heating at 18 C
    local = pd.DatetimeIndex(hourly["time_local"])
    noon = local.hour == 12
    christmas = hourly.loc[noon & (local.normalize() == "2024-12-25"), "x"].item()     # Wednesday, holiday
    sunday = hourly.loc[noon & (local.normalize() == "2024-12-22"), "x"].item()
    wednesday = hourly.loc[noon & (local.normalize() == "2024-12-18"), "x"].item()
    assert christmas == pytest.approx(sunday, rel=0.01)
    assert wednesday > 2 * christmas


def test_real_opening_hours_close_the_building_outside_them():
    hourly, _ = baseline.run(one("bar", hours_weekday="20-2", hours_saturday="closed", hours_sunday="closed"),
                             2024, np.full(8784, 18.0), LIB)
    local = pd.DatetimeIndex(hourly["time_local"])
    wed = local.normalize() == "2024-03-13"
    by_hour = hourly.loc[wed, "x"].to_numpy()
    assert by_hour[21] > 2 * by_hour[12]          # open at night, closed at noon
    assert by_hour[1] > 1.5 * by_hour[3]          # open until 2:00 (fridges keep the night level high)


def test_bills_set_the_yearly_total():
    hourly, summary = baseline.run(one("restaurant", annual_kwh="50000"), 2024, TEMP_2024, LIB)
    assert hourly["x"].sum() == pytest.approx(50000, rel=1e-3)
    assert "bills" in summary.loc[0, "label"]


def test_closed_in_august_and_school_holidays():
    hourly, _ = baseline.run(pd.concat([one("restaurant", closed_august="yes").assign(id="r"),
                                        one("school").assign(id="s")]), 2024, np.full(8784, 18.0), LIB)
    local = pd.DatetimeIndex(hourly["time_local"])
    lunch = local.hour == 14
    aug = hourly.loc[lunch & (local.normalize() == "2024-08-07"), "r"].item()
    may = hourly.loc[lunch & (local.normalize() == "2024-05-08"), "r"].item()
    assert may > 2 * aug
    july = hourly.loc[(local.hour == 10) & (local.normalize() == "2024-07-10"), "s"].item()
    march = hourly.loc[(local.hour == 10) & (local.normalize() == "2024-03-13"), "s"].item()
    assert march > 2 * july


def test_office_short_summer_hours():
    hourly, _ = baseline.run(one("office"), 2024, np.full(8784, 18.0), LIB)
    local = pd.DatetimeIndex(hourly["time_local"])
    h17 = local.hour == 17
    july = hourly.loc[h17 & (local.normalize() == "2024-07-10"), "x"].item()
    march = hourly.loc[h17 & (local.normalize() == "2024-03-13"), "x"].item()
    assert march > 1.5 * july


def test_air_conditioning_adds_use_on_hot_days():
    cool, _ = baseline.run(one("office"), 2024, np.full(8784, 18.0), LIB)
    hot, _ = baseline.run(one("office"), 2024, np.full(8784, 32.0), LIB)
    assert hot["x"].sum() > 1.2 * cool["x"].sum()


def test_hotel_keeps_ac_on_at_night_and_gym_is_quiet_at_night():
    hot = np.full(8784, 30.0)
    hotel, _ = baseline.run(one("hotel"), 2024, hot, LIB)
    office, _ = baseline.run(one("office"), 2024, hot, LIB)
    night = pd.DatetimeIndex(hotel["time_local"]).hour == 3
    # guests sleep in the hotel: its 3 am use is a much bigger part of its day than an office's
    assert hotel["x"][night].mean() / hotel["x"].mean() > 1.3 * office["x"][night].mean() / office["x"].mean()
    gym, _ = baseline.run(one("gym", hours_weekday="7-22"), 2024, TEMP_2024, LIB)
    h = pd.DatetimeIndex(gym["time_local"]).hour
    wd = gym["day_type"].to_numpy() == "weekday"
    assert gym["x"][wd & (h == 19)].mean() > 2 * gym["x"][wd & (h == 3)].mean()


def test_unknown_type_is_an_error():
    with pytest.raises(ValueError, match="Unknown type"):
        baseline.run(one("spaceport"), 2024, TEMP_2024, LIB)


# ---------- the check against open data ----------

def test_open_data_reader_and_patterns(tmp_path):
    rows = []
    for d in pd.date_range("2024-01-01", "2024-12-31"):
        for sector, scale in (("Residencial", 1.0), ("Serveis", 2.0)):
            for b, band in enumerate(["De 00:00:00 a 05:59:59 h", "De 06:00:00 a 11:59:59 h",
                                      "De 12:00:00 a 17:59:59 h", "De 18:00:00 a 23:59:59 h"]):
                rows.append([2024, d.date().isoformat(), "08018", sector, band, int(100 * scale * (b + 1))])
    path = tmp_path / "energy.csv"
    pd.DataFrame(rows, columns=["year", "Data", "Codi_Postal", "Sector_Economic", "Tram_Horari", "Valor"]).to_csv(path, index=False)
    real = check_bcn.read_open_data(path, "08018")
    ratio, shares, months = check_bcn.patterns(real["services"])
    assert ratio["sunday"] == pytest.approx(1.0)
    assert shares["weekday"] == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert len(months) == 12


# ---------- Catastro fill (with a fake Catastro, no internet) ----------

from demand import catastro_fill as cf


def fake_lookup(plots):
    """plots: list of (lat, lon, info). Returns the nearest plot within 20 m, like a map click."""
    def lookup(lat, lon):
        best = min(plots, key=lambda p: cf.distance_m(lat, lon, p[0], p[1]))
        return dict(best[2]) if cf.distance_m(lat, lon, best[0], best[1]) < 20 else None
    return lookup


def test_catastro_fill_areas_and_homes():
    host = (41.3990, 2.1930)
    plots = [
        (41.3990, 2.1930, {"refcat": "HOST", "use": "4_1_office", "dwellings": 0, "floors": 6, "footprint_m2": 800, "gross_m2": 4800}),
        (41.4000, 2.1940, {"refcat": "CAFE", "use": "1_residential", "dwellings": 20, "floors": 6, "footprint_m2": 400, "gross_m2": 2400}),
        (41.3993, 2.1934, {"refcat": "FLATS1", "use": "1_residential", "dwellings": 30, "floors": 7, "footprint_m2": 500, "gross_m2": 3500}),
        (41.3986, 2.1925, {"refcat": "FLATS2", "use": "1_residential", "dwellings": 3, "floors": 3, "footprint_m2": 150, "gross_m2": 450}),
    ]
    rows = pd.DataFrame([
        {"id": "A160", "name": "host", "role": "host", "type": "office", "floor_area_m2": "1", "whole_building": "yes", "lat": host[0], "lon": host[1]},
        {"id": "N1", "name": "cafe", "role": "neighbour", "type": "bar", "floor_area_m2": "100", "whole_building": "no", "lat": 41.4000, "lon": 2.1940},
    ]).astype(str)
    out = cf.fill(rows, fake_lookup(plots), radius_m=120, step_m=30, n_homes=5, min_flats=6, log=lambda *a: None)
    by = out.set_index("id")
    assert float(by.loc["A160", "floor_area_m2"]) == 4800          # whole building -> Catastro area
    assert float(by.loc["N1", "floor_area_m2"]) == 100             # a cafe keeps its own area
    homes = out[out["type"] == "home"]
    assert set(homes["building_refcat"]) == {"CAFE", "FLATS1"}     # flats above the cafe + the scan; FLATS2 too small
    above_cafe = homes[homes["building_refcat"] == "CAFE"].iloc[0]
    assert int(above_cafe["units"]) == 20 and above_cafe["floor_area_m2"] == 20 * 85    # flats x an average flat
    assert list(homes["id"]) == ["H01", "H02"]


def test_close_radius_adds_small_homes_and_offline_lookup_downloads_nothing(tmp_path):
    host = (41.3990, 2.1930)
    plots = [
        (41.3990, 2.1930, {"refcat": "HOST", "use": "4_1_office", "dwellings": 0, "floors": 6, "footprint_m2": 800, "gross_m2": 4800}),
        (41.3986, 2.1925, {"refcat": "HOUSE", "use": "1_residential", "dwellings": 1, "floors": 2, "footprint_m2": 100, "gross_m2": 200}),
    ]
    rows = pd.DataFrame([{"id": "A160", "name": "host", "role": "host", "type": "office", "floor_area_m2": "1",
                          "whole_building": "yes", "lat": host[0], "lon": host[1]}]).astype(str)
    plain = cf.fill(rows, fake_lookup(plots), radius_m=120, step_m=30, n_homes=5, min_flats=6, log=lambda *a: None)
    close = cf.fill(rows, fake_lookup(plots), radius_m=120, step_m=30, n_homes=5, min_flats=6, log=lambda *a: None,
                    close_radius_m=100)
    assert "HOUSE" not in set(plain["building_refcat"])            # 1 flat: below --min-flats
    assert list(close.loc[close["type"] == "home", "building_refcat"]) == ["HOUSE"]
    cache = tmp_path / "cache.json"
    cache.write_text('{"points": {"41.399000,2.193000": {"refcat": "HOST", "address": "x"}}, '
                     '"plots": {"HOST": {"use": "4_1_office", "dwellings": 0, "gross_m2": 4800}}}')
    lookup = cf.catastro_lookup(cache, offline=True)
    assert lookup(41.3990, 2.1930)["gross_m2"] == 4800              # in the cache
    assert lookup(41.5, 2.2) is None                               # not in the cache: no internet call


def test_home_area_follows_the_number_of_flats():
    assert cf.home_area({"floors": 4, "footprint_m2": 100, "dwellings": 40}) == 40 * 85
    assert cf.home_area({"floors": 4, "footprint_m2": 100, "dwellings": 0}) == 300     # no count: 3 floors above shops


def test_units_give_kwh_per_flat():
    hourly, summary = baseline.run(one("home", units="10"), 2024, TEMP_2024, LIB)
    assert summary.loc[0, "kwh_per_unit_year"] == pytest.approx(summary.loc[0, "kwh_year"] / 10, abs=1)


# ---------- bills per month and the one-program command ----------

def test_monthly_bills_set_each_month():
    bills = ";".join(str(1000 + 100 * i) for i in range(12))
    hourly, summary = baseline.run(one("shop", monthly_kwh=bills), 2024, TEMP_2024, LIB)
    local = pd.DatetimeIndex(hourly["time_local"])
    per_month = hourly.groupby(local.month)["x"].sum().to_numpy()
    assert per_month[0] == pytest.approx(1000, rel=0.02)     # January (the first UTC hour is local 01:00)
    assert per_month[6] == pytest.approx(1600, rel=1e-3)
    assert "bills" in summary.loc[0, "label"]


def test_monthly_bills_need_12_numbers():
    with pytest.raises(ValueError, match="12 numbers"):
        baseline.run(one("shop", monthly_kwh="1;2;3"), 2024, TEMP_2024, LIB)


def test_program_lookup_and_accuracy_levels():
    from demand import program
    df = pd.DataFrame([{"id": "N05", "name": "Mercadona Pallars"}, {"id": "N06", "name": "Farmacia Poblenou"}])
    assert program.find_program(df, "mercadona")["id"] == "N05"
    assert program.find_program(df, "N06")["name"] == "Farmacia Poblenou"
    assert program.accuracy({"area_source": "ESTIMATE"})[0] == 1
    assert program.accuracy({"area_source": "Catastro (x)", "hours_weekday": "9-21"})[0] == 2
    assert program.accuracy({"monthly_kwh": "1 2 3 4 5 6 7 8 9 10 11 12"})[0] == 3
