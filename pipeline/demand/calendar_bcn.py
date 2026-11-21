"""The Barcelona clock: UTC hours, local time, summer time and day types.

Every file in the team pipeline uses one clock: hourly, in UTC. People in Barcelona
live by the local clock, which is UTC+1 in winter and UTC+2 in summer. This module
turns UTC hours into local hours and tells, for each local day, what kind of day it is:

    weekday   Monday to Friday, not a holiday
    saturday  Saturday, not a holiday
    sunday    Sunday
    holiday   a public holiday in Barcelona (Spain + Catalonia + the city's 2 local days)

Holidays come from data/holidays_barcelona.csv (official calendars, with the source
of every date). Only 2023-2026 are in the file: for another year, add its rows first.
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"
HOLIDAYS_CSV = DATA / "holidays_barcelona.csv"
DAY_TYPES = ("weekday", "saturday", "sunday", "holiday")


def last_sunday(year, month):
    """Date of the last Sunday of a month."""
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - 6) % 7)


def summer_time_utc(year):
    """EU summer time: from the last Sunday of March to the last Sunday of October,
    both at 01:00 UTC. Returns (start, end) as timezone-aware UTC datetimes."""
    start = datetime.combine(last_sunday(year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(last_sunday(year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return start, end


def utc_hours(year):
    """All hours of a year in UTC (8760, or 8784 in a leap year)."""
    return pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq="h", inclusive="left", tz="UTC")


def to_local(times_utc):
    """Barcelona local time (naive) for UTC times: +1 h in winter, +2 h in summer."""
    t = pd.DatetimeIndex(times_utc)
    if t.tz is None:
        t = t.tz_localize("UTC")
    offset = np.ones(len(t), dtype=int)
    for y in np.unique(t.year):
        start, end = summer_time_utc(int(y))
        offset[(t >= start) & (t < end)] = 2
    return (t.tz_convert(None) + pd.to_timedelta(offset, unit="h")), offset


@lru_cache(maxsize=1)
def holiday_table(path=str(HOLIDAYS_CSV)):
    table = pd.read_csv(path, parse_dates=["date"])
    table["date"] = table["date"].dt.date
    return table


def holidays(years=None):
    """Set of holiday dates. Raises an error if a year is missing from the table,
    so a missing year is never silently treated as having no holidays."""
    table = holiday_table()
    if years is not None:
        known = {d.year for d in table["date"]}
        missing = sorted(set(int(y) for y in years) - known)
        if missing:
            raise ValueError(f"No holidays for {missing} in {HOLIDAYS_CSV.name}. "
                             "Add that year's official dates (Spain, Catalonia, Barcelona) first.")
    return set(table["date"])


def day_types(local_times):
    """Day type (weekday / saturday / sunday / holiday) for every local hour."""
    local = pd.DatetimeIndex(local_times)
    hol = holidays(np.unique(local.year))
    dates = local.date
    dow = local.dayofweek
    out = np.where(dow == 6, "sunday", np.where(dow == 5, "saturday", "weekday")).astype(object)
    out[np.array([d in hol for d in dates])] = "holiday"
    return out


def easter_sunday(year):
    """Easter Sunday (Gregorian calendar, the 'anonymous' algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def closed_days(kind, local_times):
    """True on days a school or a university is closed (besides weekends and holidays).

    ASSUMPTION (typical Catalan calendars, check against the real centre):
    - school: summer 21 June - 10 September, Christmas 22 December - 7 January,
      Easter week (Monday before Easter to Easter Monday).
    - university: August, and 24 December - 6 January.
    """
    local = pd.DatetimeIndex(local_times)
    month, day = local.month, local.day
    md = month * 100 + day
    if kind == "school":
        closed = (md >= 621) & (md <= 910)
        closed |= (md >= 1222) | (md <= 107)
        for y in np.unique(local.year):
            e = easter_sunday(int(y))
            start, end = e - timedelta(days=6), e + timedelta(days=1)
            closed |= np.array([(start <= d <= end) for d in local.date]) & (local.year == y)
        return closed
    if kind == "university":
        return (month == 8) | (md >= 1224) | (md <= 106)
    return np.zeros(len(local), dtype=bool)
