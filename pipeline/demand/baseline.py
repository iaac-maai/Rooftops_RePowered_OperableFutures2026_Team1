"""Baseline demand: each neighbour's electricity use, hour by hour, from Spanish schedules.

This is the "no AI" model: what a careful engineer would predict from the building type,
floor area, opening hours, the Barcelona calendar and the weather. The AI model is later
compared against it. The method follows the City Energy Analyst (CEA, ETH Zurich, MIT
licence): use = schedule x W per m2 x floor area. The schedules, holidays, summer time and
the air-conditioning term are ours, for Barcelona.

For every hour (local Barcelona time):

    share    = schedule[type][day type][hour]          0..1, from data/schedules.csv
    internal = area * ((appliances + lighting) * share * month factor + always_on) / 1000
    on       = s + (1 - s) * (how far the building is above its night level), s = hvac_min_on
               (0.15; hotels 0.8 because guests sleep there)
    T24      = mean outdoor temperature of the last 24 hours (walls and floors store heat,
               so AC and heating follow the last day's weather, not the hour's)
    ac_heat  = area * (cooling * max(0, T24 - t_cool) + heating * max(0, t_heat - T24)) * on / 1000
    kWh      = internal + ac_heat

Day types: holidays use the Sunday schedule (x holiday_factor). Schools and universities
use the Sunday schedule on the days they are closed. Offices use short hours (8-15) on
weekdays in July and August. A neighbour's real opening hours, when known, replace the
type's schedule outside them (inside them the type's shape stays, at least half of peak). Bills, when known, set the totals: yearly (annual_kwh) or month by month (monthly_kwh).

All numbers in data/*.csv are ASSUMPTIONS until checked (see check_bcn.py and README.md).
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from demand import calendar_bcn as cal

DATA = Path(__file__).parent / "data"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_SCHEDULES = ("weekday", "saturday", "sunday")
HVAC_SETBACK = 0.15
OPEN_MIN_SHARE = 0.5      # an open business uses at least half of its peak
THERMAL_MASS_HOURS = 24   # AC/heating follow the mean temperature of the last 24 hours


@dataclass
class Library:
    types: pd.DataFrame        # one row per type (data/use_types.csv)
    schedules: dict            # type -> {day type -> array(24)}
    monthly: pd.DataFrame      # type -> 12 month factors

    @classmethod
    def load(cls, folder=DATA):
        folder = Path(folder)
        types = pd.read_csv(folder / "use_types.csv").set_index("type")
        types["summer_hours"] = types["summer_hours"].fillna("")
        sch = pd.read_csv(folder / "schedules.csv")
        schedules = {t: {d: sch.loc[sch.day_type == d, t].to_numpy(float) for d in DAY_SCHEDULES}
                     for t in types.index}
        monthly = pd.read_csv(folder / "monthly.csv").set_index("type")[MONTHS]
        for t in types.index:
            for d in DAY_SCHEDULES:
                if len(schedules[t][d]) != 24:
                    raise ValueError(f"schedules.csv: {t} / {d} needs 24 hours")
        return cls(types, schedules, monthly)


def parse_hours(text):
    """'9-14,17-21' -> 24 booleans (open hours, local time). 'closed' -> all False.
    '20-2' crosses midnight. Empty -> None (use the type's schedule)."""
    if text is None or (isinstance(text, float) and np.isnan(text)) or str(text).strip() == "":
        return None
    text = str(text).strip().lower()
    open_ = np.zeros(24, dtype=bool)
    if text in ("closed", "no", "0"):
        return open_
    for part in text.replace(" ", "").split(","):
        a, b = (int(float(x)) for x in part.split("-"))
        hours = range(a, b) if b > a else list(range(a, 24)) + list(range(0, b))
        open_[[h % 24 for h in hours]] = True
    return open_


def _yes(value):
    return str(value).strip().lower() in ("yes", "y", "true", "1", "si", "sí")


@dataclass
class Clock:
    """Everything about the hours of one year, computed once and shared by all neighbours."""
    utc: pd.DatetimeIndex
    local: pd.DatetimeIndex
    hour: np.ndarray
    month: np.ndarray
    day_type: np.ndarray       # weekday / saturday / sunday / holiday

    @classmethod
    def for_year(cls, year):
        utc = cal.utc_hours(year)
        local, _ = cal.to_local(utc)
        return cls(utc, local, local.hour.to_numpy(), local.month.to_numpy(), cal.day_types(local))


def hourly_share(row, lib, clock):
    """Share of peak use (0..1) for every hour, for one neighbour."""
    kind = row["type"]
    t = lib.types.loc[kind]
    sched = lib.schedules[kind]
    # which of the 3 day schedules each hour follows
    use = np.where(clock.day_type == "holiday", "sunday", clock.day_type).astype(object)
    if t["closed_calendar"] in ("school", "university"):
        use[cal.closed_days(t["closed_calendar"], clock.local) & (use != "sunday")] = "sunday"
    share = np.zeros(len(use))
    for d in DAY_SCHEDULES:
        m = use == d
        share[m] = sched[d][clock.hour[m]]

    # office short summer hours: July-August weekdays, open only inside summer_hours
    summer = parse_hours(t["summer_hours"]) if t["summer_hours"] else None
    if summer is not None:
        m = (use == "weekday") & np.isin(clock.month, (7, 8)) & ~summer[clock.hour]
        share[m] = np.minimum(share[m], sched["saturday"][clock.hour[m]])

    # the neighbour's real opening hours, when known: outside them the building is at its
    # night level; inside them it keeps the type's shape (e.g. meal peaks), at least OPEN_MIN_SHARE
    base = {d: float(sched[d].min()) for d in DAY_SCHEDULES}
    for d, col in (("weekday", "hours_weekday"), ("saturday", "hours_saturday"), ("sunday", "hours_sunday")):
        open_ = parse_hours(row.get(col))
        if open_ is None:
            continue
        m = use == d
        share[m] = np.where(open_[clock.hour[m]], np.maximum(share[m], OPEN_MIN_SHARE), base[d])

    if _yes(row.get("closed_august", "")):
        m = clock.month == 8
        share[m] = base["sunday"]
    night = min(base.values())
    return share, night


def neighbour_hourly(row, lib, clock, temp_C):
    """Hourly kWh for one neighbour (numpy array, one value per UTC hour)."""
    t = lib.types.loc[row["type"]]
    area = float(row["floor_area_m2"])
    share, night = hourly_share(row, lib, clock)
    month_f = lib.monthly.loc[row["type"]].to_numpy(float)[clock.month - 1]
    hol_f = np.where(clock.day_type == "holiday", float(t["holiday_factor"]), 1.0)
    internal = area * ((t["appliances_Wm2"] + t["lighting_Wm2"]) * share * month_f * hol_f + t["always_on_Wm2"]) / 1000
    # AC/heating at least at the type's minimum (hotels: guests sleep there, so AC runs at night)
    setback = float(t["hvac_min_on"]) if "hvac_min_on" in t and pd.notna(t["hvac_min_on"]) else HVAC_SETBACK
    on = setback + (1 - setback) * np.clip((share - night) / max(1 - night, 1e-6), 0, 1)
    T = pd.Series(np.asarray(temp_C, float)).rolling(THERMAL_MASS_HOURS, min_periods=1).mean().to_numpy()
    ac_heat = area * (t["cooling_Wm2K"] * np.maximum(0, T - t["t_cool_C"])
                      + t["heating_Wm2K"] * np.maximum(0, t["t_heat_C"] - T)) * on / 1000
    kwh = internal + ac_heat
    annual = row.get("annual_kwh")
    if annual is not None and not (isinstance(annual, float) and np.isnan(annual)) and str(annual).strip() != "":
        kwh = kwh * float(annual) / kwh.sum()
    monthly = parse_monthly(row.get("monthly_kwh"))
    if monthly is not None:                      # bills for each month: each month's total is measured
        for mo in range(1, 13):
            m = clock.month == mo
            if m.any() and kwh[m].sum() > 0:
                kwh[m] = kwh[m] * monthly[mo - 1] / kwh[m].sum()
    return kwh


def parse_monthly(text):
    """'900;850;...' (12 numbers, January to December) -> array, or None if empty."""
    if text is None or (isinstance(text, float) and np.isnan(text)) or str(text).strip() == "":
        return None
    values = [float(v) for v in str(text).replace(";", " ").split()]
    if len(values) != 12:
        raise ValueError(f"monthly_kwh needs 12 numbers (January to December), got {len(values)}")
    return np.array(values)


def read_neighbours(path):
    """One row = one consumer: a program with its own meter(s), e.g. a cafe, or the flats of
    one building (units = number of flats). Several rows can share one building."""
    df = pd.read_csv(path, dtype=str, comment="#").fillna("")
    df.columns = [c.strip() for c in df.columns]
    for col in ("id", "type", "floor_area_m2"):
        if col not in df.columns:
            raise ValueError(f"{path}: column '{col}' is missing")
    df["type"] = df["type"].str.strip().str.lower()
    df["floor_area_m2"] = df["floor_area_m2"].astype(float)
    return df


def run(neighbours, year, temp_C, lib=None):
    """Hourly kWh for all neighbours. Returns (hourly table, summary table)."""
    lib = lib or Library.load()
    clock = Clock.for_year(year)
    unknown = sorted(set(neighbours["type"]) - set(lib.types.index))
    if unknown:
        raise ValueError(f"Unknown type(s) {unknown}. Known: {list(lib.types.index)}")
    hourly = pd.DataFrame({"time_utc": clock.utc, "time_local": clock.local, "day_type": clock.day_type})
    rows = []
    for _, r in neighbours.iterrows():
        kwh = neighbour_hourly(r, lib, clock, temp_C)
        hourly[r["id"]] = np.round(kwh, 3)
        sunny = (clock.hour >= 10) & (clock.hour < 17)
        weekend = np.isin(clock.day_type, ("saturday", "sunday", "holiday"))
        has_bills = str(r.get("annual_kwh", "")).strip() != "" or str(r.get("monthly_kwh", "")).strip() != ""
        units = pd.to_numeric(r.get("units", ""), errors="coerce")
        units = int(units) if pd.notna(units) and units > 0 else 1
        rows.append({
            "id": r["id"], "name": r.get("name", ""), "role": r.get("role", ""), "type": r["type"],
            "floor_area_m2": r["floor_area_m2"], "units": units, "kwh_year": round(kwh.sum()),
            "kwh_per_unit_year": round(kwh.sum() / units),
            "kwh_per_m2_year": round(kwh.sum() / r["floor_area_m2"], 1), "peak_kw": round(kwh.max(), 1),
            "share_10_17h": round(kwh[sunny].sum() / kwh.sum(), 3),
            "share_weekend_holiday": round(kwh[weekend].sum() / kwh.sum(), 3),
            "label": "modeled (bills set the yearly total)" if has_bills else "modeled (assumed W/m2)",
        })
    return hourly, pd.DataFrame(rows)
