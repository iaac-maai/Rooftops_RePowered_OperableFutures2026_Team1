"""Hourly outdoor temperature for Barcelona, in UTC, for one real year.

The demand model needs the temperature of the SAME real year as the solar output
(team rule: one clock, one year). Run this on a laptop with internet:

    python -m demand.weather --year 2024          # -> data/weather/temperature_2024.csv

The data comes from Open-Meteo's historical weather archive (ERA5 reanalysis,
free, no key). An EPW file also works (python -m demand.run --weather file.epw),
but a "typical year" EPW mixes months from different years, so its days of the
week and holidays do not match a real calendar. Use it only to test.

synthetic_barcelona() makes a smooth made-up year from rough monthly averages.
It exists ONLY so the code can be tested without internet. Never use it for results.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from demand.calendar_bcn import utc_hours

LAT, LON = 41.4005, 2.1935      # Carrer dels Almogavers 160, Poblenou
WEATHER_DIR = Path("data/weather")
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def csv_path(year):
    return WEATHER_DIR / f"temperature_{year}.csv"


def download(year, lat=LAT, lon=LON, out=None):
    import requests
    params = {"latitude": lat, "longitude": lon, "start_date": f"{year}-01-01",
              "end_date": f"{year}-12-31", "hourly": "temperature_2m", "timezone": "GMT"}
    r = requests.get(ARCHIVE_URL, params=params, timeout=120)
    r.raise_for_status()
    h = r.json()["hourly"]
    df = pd.DataFrame({"time_utc": pd.to_datetime(h["time"], utc=True), "temp_C": h["temperature_2m"]})
    out = Path(out or csv_path(year))
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out


def read_csv(path):
    df = pd.read_csv(path, parse_dates=["time_utc"])
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df.set_index("time_utc")["temp_C"].astype(float)


def read_epw(path, year=None):
    """Dry-bulb temperature from an EPW file. EPW hours are local standard time
    (UTC+1 for Barcelona), numbered 1-24 for the hour that ENDS at that time."""
    rows = pd.read_csv(path, skiprows=8, header=None)
    temp = rows[6].astype(float).to_numpy()
    year = year or int(rows[0].iloc[0])
    start = pd.Timestamp(f"{year}-01-01 00:00", tz="UTC") - pd.Timedelta(hours=1)
    idx = pd.date_range(start, periods=len(temp), freq="h")
    return pd.Series(temp, index=idx, name="temp_C")


# Rough monthly means for central Barcelona (deg C). Test data only.
_MONTHLY_MEAN = [10.5, 11.2, 13.4, 15.6, 19.0, 22.9, 25.8, 26.2, 23.0, 19.3, 14.6, 11.4]


def synthetic_barcelona(year):
    """A made-up but plausible year: monthly means + a daily swing of +-3.5 C
    (coolest around 06:00, warmest around 15:00 local). TEST ONLY."""
    t = utc_hours(year)
    doy = (t.dayofyear.to_numpy() - 1) + t.hour.to_numpy() / 24
    mid = np.array([15, 45, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349], float)
    mean = np.interp(doy, np.r_[mid - 365, mid, mid + 365], np.tile(_MONTHLY_MEAN, 3))
    local_hour = (t.hour.to_numpy() + 1) % 24
    swing = 3.5 * np.cos(2 * np.pi * (local_hour - 15) / 24)
    return pd.Series(mean + swing, index=t, name="temp_C")


def load(year, source=None):
    """Temperature for every UTC hour of `year`.

    source: None (use data/weather/temperature_<year>.csv), a .csv or .epw path,
    or "synthetic" (test only)."""
    hours = utc_hours(year)
    if source == "synthetic":
        return synthetic_barcelona(year), "SYNTHETIC test weather (not real)"
    path = Path(source) if source else csv_path(year)
    if not path.exists():
        raise FileNotFoundError(f"No weather file {path}. Run: python -m demand.weather --year {year}")
    if path.suffix.lower() == ".epw":
        temp, label = read_epw(path, year), f"EPW file {path.name} (typical year, test only)"
    else:
        temp, label = read_csv(path), f"Open-Meteo ERA5 {year} ({path.name})"
    temp = temp.reindex(hours).interpolate(limit_direction="both")
    return temp, label


def main():
    ap = argparse.ArgumentParser(description="Download one real year of hourly temperature for Barcelona")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--lat", type=float, default=LAT)
    ap.add_argument("--lon", type=float, default=LON)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = download(a.year, a.lat, a.lon, a.out)
    temp = read_csv(out)
    print(f"{len(temp)} hours, mean {temp.mean():.1f} C, min {temp.min():.1f}, max {temp.max():.1f} -> {out}")


if __name__ == "__main__":
    main()
