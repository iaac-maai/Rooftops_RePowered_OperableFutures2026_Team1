"""One program in, its whole year of hourly electricity out.

    python -m demand.program N05                          # by id, from the neighbours file
    python -m demand.program Mercadona                    # or by (part of) the name
    python -m demand.program --type bar --area 120 --weekday 8-20 --saturday 9-16 --sunday 9-16
                                                          # or a new program that is not in the list

Writes to data/programs/:
    <id>_<year>.csv   every hour of the year: time_utc, time_local, day_type, temp_C, kwh
    <id>_<year>.png   average day (weekday / Saturday / Sunday-holiday), two sample weeks,
                      kWh per month, and the whole year as a carpet (day x hour)

How exact is it? The printout says what the numbers rest on:
    level 1  type only (area and hours estimated)
    level 2  real floor area (Catastro) and real opening hours
    level 3  plus bills: the yearly or monthly totals are measured, the hours are modeled
    Exact hourly data exists only in the program's own meter (Datadis, with the owner's consent).
"""
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from demand import baseline, weather

DEFAULT_LISTS = [Path("demand/neighbours_a160_catastro.csv"), Path("demand/neighbours_a160.csv")]


def find_program(neighbours, key):
    """Row whose id matches exactly, else whose name contains `key` (case-insensitive)."""
    hit = neighbours[neighbours["id"].str.lower() == key.lower()]
    if hit.empty:
        hit = neighbours[neighbours["name"].str.lower().str.contains(key.lower(), regex=False)]
    if hit.empty:
        raise SystemExit(f"No program '{key}'. Ids: {', '.join(neighbours['id'])}")
    if len(hit) > 1:
        raise SystemExit(f"'{key}' matches {len(hit)} programs: {', '.join(hit['id'] + ' ' + hit['name'])}. Use the id.")
    return hit.iloc[0]


def accuracy(row):
    has = lambda c: str(row.get(c, "")).strip() not in ("", "nan")
    area_real = "catastro" in str(row.get("area_source", "")).lower() or "bill" in str(row.get("area_source", "")).lower()
    hours_real = any(has(c) for c in ("hours_weekday", "hours_saturday", "hours_sunday"))
    if has("monthly_kwh"):
        return 3, "level 3: monthly totals from bills; hours modeled from the opening hours"
    if has("annual_kwh"):
        return 3, "level 3: yearly total from bills; months and hours modeled"
    if str(row.get("type", "")) == "home" and area_real:
        return 2, "level 2: number of flats from Catastro; household day shape fitted on real 08018 homes"
    if area_real and hours_real:
        return 2, "level 2: Catastro floor area and real opening hours; totals modeled"
    if area_real or hours_real:
        return 2, "level 2 (partly): " + ("Catastro area" if area_real else "real opening hours") + "; the rest estimated"
    return 1, "level 1: type only; area and hours are estimates"


def plot(df, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    local = pd.DatetimeIndex(df["time_local"])
    fig = plt.figure(figsize=(13, 9))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.25])

    ax = fig.add_subplot(gs[0, 0])
    for kind, colour in (("weekday", "#2b6cb0"), ("saturday", "#ed8936"), ("sunday", "#38a169")):
        m = df["day_type"].isin(["sunday", "holiday"]) if kind == "sunday" else df["day_type"] == kind
        ax.plot(range(24), df[m].groupby(local[m].hour)["kwh"].mean(), color=colour, lw=2,
                label="Sunday / holiday" if kind == "sunday" else kind.capitalize())
    ax.set_title("Average day (local time)", loc="left", fontsize=10)
    ax.set_xticks(range(0, 24, 3))
    ax.set_ylabel("kWh per hour")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    ax = fig.add_subplot(gs[0, 1])
    monthly = df.groupby(local.month)["kwh"].sum() / 1000
    ax.bar(monthly.index, monthly.values, color="#4a5568")
    ax.set_xticks(range(1, 13), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_title("Per month (MWh)", loc="left", fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    for col, month in ((0, 2), (1, 7)):
        ax = fig.add_subplot(gs[1, col])
        mondays = local[(local.month == month) & (local.dayofweek == 0) & (local.hour == 0)]
        start = mondays[1] if len(mondays) > 1 else local[local.month == month][0]
        m = (local >= start) & (local < start + pd.Timedelta(days=7))
        ax.plot(local[m], df.loc[m, "kwh"], color="#2b6cb0", lw=1.4)
        hol = m & (df["day_type"] == "holiday").to_numpy()
        if hol.any():
            ax.scatter(local[hol], df.loc[hol, "kwh"], s=6, color="#e53e3e", label="holiday")
            ax.legend(fontsize=8)
        ax.set_title(f"A week in {'February' if month == 2 else 'July'}", loc="left", fontsize=10)
        ax.tick_params(axis="x", labelsize=7)
        ax.grid(alpha=0.3)

    ax = fig.add_subplot(gs[2, :])
    year = local[len(local) // 2].year
    keep = (local.year == year)
    local, kwh_values = local[keep], df["kwh"].to_numpy()[keep]
    days = pd.Index(local.normalize().unique())
    carpet = np.full((24, len(days)), np.nan)
    pos = {d: i for i, d in enumerate(days)}
    carpet[local.hour, [pos[d] for d in local.normalize()]] = kwh_values
    carpet = pd.DataFrame(carpet).ffill().bfill().to_numpy()   # the hour skipped by summer time
    im = ax.imshow(carpet, aspect="auto", origin="lower", cmap="magma",
                   extent=[0, len(days), 0, 24])
    ax.set_yticks(range(0, 25, 6))
    ax.set_ylabel("hour")
    month_starts = [i for i, d in enumerate(days) if d.day == 1]
    ax.set_xticks(month_starts, [days[i].strftime("%b") for i in month_starts])
    ax.set_title("The whole year, every hour (bright = more kWh)", loc="left", fontsize=10)
    fig.colorbar(im, ax=ax, label="kWh", pad=0.01)

    fig.suptitle(title, fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser(description="Hourly electricity of one program, for a whole year")
    ap.add_argument("program", nargs="?", help="id or part of the name, from the neighbours file")
    ap.add_argument("--neighbours", help="default: demand/neighbours_a160_catastro.csv, else demand/neighbours_a160.csv")
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--weather", default=None, help="default data/weather/temperature_<year>.csv")
    ap.add_argument("--out", default="data/programs")
    new = ap.add_argument_group("a new program (instead of one from the list)")
    new.add_argument("--type")
    new.add_argument("--area", type=float, help="floor area in m2")
    new.add_argument("--name", default="new program")
    new.add_argument("--weekday", default="")
    new.add_argument("--saturday", default="")
    new.add_argument("--sunday", default="")
    new.add_argument("--annual-kwh", default="")
    new.add_argument("--monthly-kwh", default="", help="12 numbers from bills, Jan to Dec, e.g. 900;850;...")
    a = ap.parse_args()

    if a.type:
        if not a.area:
            raise SystemExit("A new program needs --type and --area.")
        row = pd.Series({"id": re.sub(r"\W+", "_", a.name).strip("_") or "new", "name": a.name, "type": a.type.lower(),
                         "floor_area_m2": a.area, "hours_weekday": a.weekday, "hours_saturday": a.saturday,
                         "hours_sunday": a.sunday, "annual_kwh": a.annual_kwh, "monthly_kwh": a.monthly_kwh,
                         "area_source": "given", "units": ""})
    else:
        if not a.program:
            raise SystemExit("Give a program id or name, or a new program with --type and --area.")
        path = Path(a.neighbours) if a.neighbours else next((p for p in DEFAULT_LISTS if p.exists()), None)
        if path is None:
            raise SystemExit("No neighbours file found; give one with --neighbours.")
        row = find_program(baseline.read_neighbours(path), a.program)

    temp, weather_label = weather.load(a.year, a.weather)
    hourly, summary = baseline.run(pd.DataFrame([row]), a.year, temp.to_numpy())
    pid = str(row["id"])
    df = hourly[["time_utc", "time_local", "day_type"]].copy()
    df["temp_C"] = np.round(temp.to_numpy(), 1)
    df["kwh"] = hourly[pid]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{pid}_{a.year}.csv"
    df.to_csv(csv_path, index=False)
    level, why = accuracy(row)
    s = summary.iloc[0]
    title = f"{row['name']} ({row['type']}, {float(row['floor_area_m2']):,.0f} m2), {a.year}"
    png = plot(df, title, out / f"{pid}_{a.year}.png")

    print(title)
    print(f"  {s['kwh_year']:,.0f} kWh a year, {s['kwh_per_m2_year']} kWh/m2, peak {s['peak_kw']} kW")
    print(f"  {100 * s['share_10_17h']:.0f}% of it between 10:00 and 17:00, "
          f"{100 * s['share_weekend_holiday']:.0f}% at weekends and holidays")
    print(f"  based on: {why}")
    print(f"  weather: {weather_label}")
    print(f"-> {csv_path} ({len(df)} hours), {png}")


if __name__ == "__main__":
    main()
