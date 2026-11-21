"""Run the baseline for a list of neighbours: one command, hourly kWh for a whole year.

    python -m demand.weather --year 2024                       # once, needs internet
    python -m demand.run --neighbours demand/neighbours_example.csv --year 2024

Writes to data/demand/:
    demand_baseline_hourly.csv   one row per UTC hour, one column per neighbour (kWh)
    neighbours_summary.csv       yearly kWh, kWh/m2, peak kW, share used 10-17 h and at weekends
    run_info.json                year, weather source and labels (every number here is "modeled")
    typical_weeks.png            a winter week and a summer week, to look at the shapes
"""
import argparse
import json
from pathlib import Path

from demand import baseline, weather


MAX_LINES = 11      # with many programs the chart shows the first (host) and the 10 biggest users


def plot_weeks(hourly, ids, path):
    ids = list(ids)
    if len(ids) > MAX_LINES:
        rest = sorted(ids[1:], key=lambda i: hourly[i].sum(), reverse=True)[:MAX_LINES - 1]
        ids = [ids[0]] + rest
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    local = hourly["time_local"]
    year = local.iloc[len(local) // 2].year
    weeks = {"winter week (from 2nd Monday of February)": f"{year}-02-01",
             "summer week (from 2nd Monday of July)": f"{year}-07-01"}
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharey=True)
    for ax, (title, start) in zip(axes, weeks.items()):
        first = local[local >= start]
        mondays = first[first.dt.dayofweek == 0]
        t0 = mondays.iloc[24] if len(mondays) > 24 else first.iloc[0]
        m = (local >= t0) & (local < t0 + __import__("pandas").Timedelta(days=7))
        colours = plt.get_cmap("tab20").colors
        for k, i in enumerate(ids):
            ax.plot(local[m], hourly.loc[m, i], label=i, lw=1.4, color=colours[k % len(colours)])
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_ylabel("kWh per hour")
        ax.grid(alpha=0.3)
    axes[0].legend(ncol=1, fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.suptitle("Baseline demand (modeled, local Barcelona time)"
                 + (f": host and the {len(ids) - 1} biggest users" if len(ids) == MAX_LINES else ""), fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser(description="Baseline hourly demand of the neighbours")
    ap.add_argument("--neighbours", required=True, help="CSV, see demand/neighbours_example.csv")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--weather", default=None,
                    help="default data/weather/temperature_<year>.csv; or a .csv/.epw path; or 'synthetic' (test only)")
    ap.add_argument("--out", default="data/demand")
    a = ap.parse_args()

    neighbours = baseline.read_neighbours(a.neighbours)
    temp, weather_label = weather.load(a.year, a.weather)
    hourly, summary = baseline.run(neighbours, a.year, temp.to_numpy())

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(out / "demand_baseline_hourly.csv", index=False)
    summary.to_csv(out / "neighbours_summary.csv", index=False)
    info = {"year": a.year, "weather": weather_label, "clock": "time_utc is UTC; time_local is Barcelona time",
            "label": "modeled: baseline from Spanish schedules (no AI)",
            "neighbours_file": str(a.neighbours), "hours": len(hourly)}
    (out / "run_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    png = plot_weeks(hourly, list(neighbours["id"]), out / "typical_weeks.png")

    print(f"weather: {weather_label}")
    print(summary[["id", "type", "floor_area_m2", "units", "kwh_year", "kwh_per_m2_year", "peak_kw",
                   "share_10_17h", "share_weekend_holiday"]].to_string(index=False))
    print(f"-> {out / 'demand_baseline_hourly.csv'} ({len(hourly)} hours)" + (f", {png}" if png else ""))
    if weather_label.startswith("SYNTHETIC"):
        print("WARNING: synthetic weather. Only for testing; download the real year first.")


if __name__ == "__main__":
    main()
