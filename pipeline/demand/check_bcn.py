"""Check the baseline against real Barcelona meter data (Datadis, via Open Data BCN).

    python -m demand.check_bcn --energy "path/to/energy_clean.csv" --years 2023 2024

The open data gives, for every day and postal code, the electricity used by homes and by
services in 4 time bands (00-06, 06-12, 12-18, 18-24 local time). It has no buildings and
no hours, so it cannot train a model, but it is the best real test of the PATTERN:

  1. day types: Saturday, Sunday and holidays compared with a normal weekday
  2. time bands: how each day type's use splits over the 4 bands
  3. months: each month's daily use compared with the year's average

Homes are compared with the "Residencial" sector. Services are compared with a mix of
our types (offices, shops, restaurants...). The mix is an ASSUMPTION for 08018 (22@
district, many offices), set with --mix. The open data counts kWh (not MWh, as its title
says: the city total is about 6 billion a year, which only fits kWh).
"""
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from demand import baseline, weather
from demand import calendar_bcn as cal

DEFAULT_MIX = {"office": 0.50, "shop": 0.12, "supermarket": 0.05, "restaurant": 0.08,
               "bar": 0.07, "cinema": 0.01, "school": 0.07, "university": 0.10}
SECTORS = {"home": "Residencial", "services": "Serveis"}
BANDS = ["00-06", "06-12", "12-18", "18-24"]


def read_open_data(path, postal="08018"):
    """Daily kWh per time band for homes and services in one postal code."""
    df = pd.read_csv(path, dtype=str)
    df.columns = [re.sub(r"^\d+\.", "", c.strip().lstrip("﻿")) for c in df.columns]
    df = df[df["Codi_Postal"].str.zfill(5) == postal]
    df = df[df["Tram_Horari"].str.contains(r"\d", na=False)]
    df["band"] = df["Tram_Horari"].str.extract(r"(\d{1,2}):")[0].astype(int) // 6
    df["date"] = pd.to_datetime(df["Data"]).dt.date
    df["kwh"] = df["Valor"].str.replace(",", ".").astype(float)
    out = {}
    for key, sector in SECTORS.items():
        s = df[df["Sector_Economic"] == sector]
        out[key] = s.pivot_table(index="date", columns="band", values="kwh", aggfunc="sum").sort_index()
    return out


def model_bands(year, temp_source, mix, lib):
    """The same daily x band tables, from the baseline model."""
    rows = [{"id": "home", "type": "home", "floor_area_m2": 1000.0}]
    rows += [{"id": f"svc_{t}", "type": t, "floor_area_m2": 1000.0 * w} for t, w in mix.items()]
    neighbours = pd.DataFrame(rows)
    temp, label = weather.load(year, temp_source)
    hourly, _ = baseline.run(neighbours, year, temp.to_numpy(), lib)
    local = pd.DatetimeIndex(hourly["time_local"])
    hourly["date"], hourly["band"] = local.date, local.hour // 6
    svc_cols = [c for c in hourly.columns if c.startswith("svc_")]
    hourly["services"] = hourly[svc_cols].sum(axis=1)
    out = {k: hourly.pivot_table(index="date", columns="band", values=k, aggfunc="sum")
           for k in ("home", "services")}
    year_days = [d for d in out["home"].index if d.year == year]
    return {k: v.loc[year_days] for k, v in out.items()}, label


def patterns(daily_bands):
    """Day-type ratios, band shares (August left out) and month factors."""
    d = daily_bands.copy()
    dates = pd.to_datetime(pd.Index(d.index))
    dtype = cal.day_types(dates)
    total = d.sum(axis=1)
    not_aug = dates.month != 8
    ratio = {t: total[(dtype == t) & not_aug].mean() / total[(dtype == "weekday") & not_aug].mean()
             for t in ("saturday", "sunday", "holiday")}
    shares = {}
    for t in cal.DAY_TYPES:
        m = (dtype == t) & not_aug
        s = d[m].sum()
        shares[t] = (s / s.sum()).to_numpy()
    monthly = total.groupby(dates.month).mean()
    return ratio, shares, (monthly / monthly.mean()).to_numpy()


def compare(real, model):
    rr, rs, rm = patterns(real)
    mr, ms, mm = patterns(model)
    lines = []
    for t in ("saturday", "sunday", "holiday"):
        lines.append({"what": f"{t} vs weekday", "real": rr[t], "model": mr[t]})
    for t in cal.DAY_TYPES:
        for b, name in enumerate(BANDS):
            lines.append({"what": f"{t} share {name}", "real": rs[t][b], "model": ms[t][b]})
    for i, name in enumerate(baseline.MONTHS):
        if i < len(rm) and i < len(mm):
            lines.append({"what": f"month {name}", "real": rm[i], "model": mm[i]})
    table = pd.DataFrame(lines)
    table["gap"] = table["model"] - table["real"]
    return table


def plot(out, postal, years, path):
    """Real vs model: the 4 time bands of each day type, and each day type vs a weekday."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    groups = ["weekday", "saturday", "sunday", "holiday"]
    for ax, key in zip(axes, ("home", "services")):
        s = out[out.sector == key].groupby("what", sort=False)[["real", "model"]].mean()
        x, labels = 0, []
        for g in groups:
            level = 1.0 if g == "weekday" else s.loc[f"{g} vs weekday"]
            for b, name in enumerate(BANDS):
                r = s.loc[f"{g} share {name}"]
                ax.bar(x - 0.2, r["real"] * (level["real"] if g != "weekday" else 1), 0.4,
                       color="#2b6cb0", label="real (Datadis)" if x == 0 else None)
                ax.bar(x + 0.2, r["model"] * (level["model"] if g != "weekday" else 1), 0.4,
                       color="#ed8936", label="model (baseline)" if x == 0 else None)
                labels.append(name)
                x += 1
            ax.text(x - 2.5, -0.11, g, ha="center", fontsize=9, transform=ax.get_xaxis_transform())
            x += 0.6
        ax.set_xticks([i + (i // 4) * 0.6 for i in range(16)], labels, fontsize=7)
        ax.set_title(f"{postal} {SECTORS[key]} ({'homes' if key == 'home' else 'services'})", loc="left", fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("share of a normal weekday's use")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Time bands and day types, real vs model, {'-'.join(map(str, years))}", fontsize=11)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.16)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser(description="Compare the baseline with real 08018 data")
    ap.add_argument("--energy", required=True, help="energy_clean.csv or an Open Data BCN yearly CSV")
    ap.add_argument("--postal", default="08018")
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024])
    ap.add_argument("--weather", default=None,
                    help="folder with temperature_<year>.csv (default data/weather), or 'synthetic' (test only)")
    ap.add_argument("--mix", default=None, help="services mix, e.g. office=0.5,shop=0.2,restaurant=0.3")
    ap.add_argument("--out", default="data/demand/check_08018.csv")
    a = ap.parse_args()
    mix = DEFAULT_MIX if not a.mix else {k: float(v) for k, v in (p.split("=") for p in a.mix.split(","))}
    lib = baseline.Library.load()
    real = read_open_data(a.energy, a.postal)
    tables = []
    for year in a.years:
        src = "synthetic" if a.weather == "synthetic" else (
            str(Path(a.weather) / f"temperature_{year}.csv") if a.weather else None)
        model, label = model_bands(year, src, mix, lib)
        for key in ("home", "services"):
            r = real[key][[d.year == year for d in real[key].index]]
            if r.empty:
                print(f"no real data for {key} in {year}")
                continue
            t = compare(r, model[key].loc[[d for d in model[key].index if d in set(r.index)]])
            t.insert(0, "sector", key)
            t.insert(0, "year", year)
            tables.append(t)
        print(f"{year}: weather = {label}")
    out = pd.concat(tables)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.round(4).to_csv(a.out, index=False)
    for key in ("home", "services"):
        s = out[out.sector == key]
        mean = s.groupby("what", sort=False)[["real", "model", "gap"]].mean()
        print(f"\n== {key} ({SECTORS[key]}), mean over {a.years}")
        print(mean.round(3).to_string())
        print(f"   day-type gap: {mean.loc[mean.index.str.contains('vs weekday'), 'gap'].abs().mean():.3f}   "
              f"band-share gap: {mean.loc[mean.index.str.contains('share'), 'gap'].abs().mean():.3f}   "
              f"month gap: {mean.loc[mean.index.str.startswith('month'), 'gap'].abs().mean():.3f}")
    png = plot(out, a.postal, a.years, Path(a.out).with_suffix(".png"))
    print(f"\n-> {a.out}" + (f", {png}" if png else ""))


if __name__ == "__main__":
    main()
