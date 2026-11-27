"""Step 09: the hourly data behind two website charts, worked out here so the browser only draws.

1. "Spare solar, every hour of the year" (spare_views): one 365-day x 24-hour grid per view, in LOCAL
   time (Europe/Madrid, with summer time), plus each view's yearly total:
     total          solar - the host's own use, where above 0             (= step 04 surplus_kwh)
     host_share     host share x solar - the host's use, where above 0     (what the host can't use of its share)
     cep9_grid      sum over members of max(0, share x solar - member's use)  (= agreed_shares to_grid_kwh)
     our_tool_grid  exported + curtailed in the battery agent's typical year  (= step 07 exported + curtailed)
   Each day is labelled with its weekday and, for the 2023 calendar, school holidays.
2. "Average day: solar and each building's use" (season_profiles): the mean day per season
   (winter Dec-Feb, spring-autumn Mar-May and Sep-Nov, summer Jun-Aug) for weekdays and weekends.

Local time: every UTC hour is converted with zoneinfo("Europe/Madrid"). On the day summer time starts
one local hour is missing (left at 0); on the day it ends two UTC hours fall in the same local hour
(added together). The grid total always equals the yearly total (see to_grid).
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

MADRID = ZoneInfo("Europe/Madrid")
SEASONS = {"winter": (12, 1, 2), "spring_autumn": (3, 4, 5, 9, 10, 11), "summer": (6, 7, 8)}
SEASON_LABELS = {"winter": "Winter (Dec-Feb)", "spring_autumn": "Spring and autumn", "summer": "Summer (Jun-Aug)"}
# Colour steps of the spare-solar grid, kWh in one hour, the same for every view (Breno, 27 Nov 2026).
COLOUR_KWH = (0, 10, 20, 30)
# School holidays on the 2023 calendar (the typical solar year is laid on 2023):
#   Christmas 22 Dec 2022 - 8 Jan 2023 and Easter 3-10 Apr 2023 [Ordre EDU/113/2022, school calendar 2022-23];
#   Christmas from 21 Dec 2023 [school calendar 2023-24, betevé];
#   summer = July and August (Breno's choice, 27 Nov 2026; lessons end around 21 June).
HOLIDAYS = {2023: [("Christmas", date(2023, 1, 1), date(2023, 1, 8)), ("Easter", date(2023, 4, 3), date(2023, 4, 10)),
                   ("Summer (Jul-Aug)", date(2023, 7, 1), date(2023, 8, 31)), ("Christmas", date(2023, 12, 21), date(2023, 12, 31))]}
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def local_parts(times_utc):
    """-> (local dates as datetime.date, local hour 0-23, weekday 0=Mon, local month 1-12)."""
    dates, hours, wdays, months = [], [], [], []
    for t in np.asarray(times_utc, dtype="datetime64[m]"):
        lt = datetime.fromisoformat(str(t)).replace(tzinfo=timezone.utc).astimezone(MADRID)
        dates.append(lt.date()); hours.append(lt.hour); wdays.append(lt.weekday()); months.append(lt.month)
    return dates, np.array(hours), np.array(wdays), np.array(months)


def day_labels(year, n_days=365):
    """[{date, weekday (0=Mon), day ('Sat 18 Feb'), weekend, holiday}] for the n_days from 1 January."""
    start = date(year, 1, 1)
    out = []
    for k in range(n_days):
        d = date.fromordinal(start.toordinal() + k)
        hol = next((name for name, a, b in HOLIDAYS.get(year, []) if a <= d <= b), None)
        out.append({"date": d.isoformat(), "weekday": d.weekday(), "day": f"{WEEKDAYS[d.weekday()]} {d.day} {d:%b}",
                    "weekend": d.weekday() >= 5, "holiday": hol})
    return out


def to_grid(dates, hours, values, year, n_days=365):
    """Hourly values -> n_days x 24 array by local date and hour. The last UTC hour of the year falls on
    1 January of the next year in local time; it is added to the last day's same hour, so the grid's
    total always equals the yearly total."""
    g = np.zeros((n_days, 24))
    start = date(year, 1, 1).toordinal()
    idx = np.clip(np.array([d.toordinal() - start for d in dates]), 0, n_days - 1)
    np.add.at(g, (idx, hours), np.asarray(values, float))
    return g


def closed_shares(grid, days):
    """Share of a grid's total that falls on weekends, on school holidays (weekdays only), and both together."""
    total = grid.sum()
    if total <= 0:
        return {"weekend": 0.0, "holiday_weekdays": 0.0, "closed": 0.0}
    we = np.array([d["weekend"] for d in days])
    hol = np.array([bool(d["holiday"]) and not d["weekend"] for d in days])
    a, b = grid[we].sum() / total, grid[hol].sum() / total
    return {"weekend": round(float(a), 3), "holiday_weekdays": round(float(b), 3), "closed": round(float(a + b), 3)}


def spare_views(times, gen, host_use, member_ids=(), member_use=None, shares=None, our_tool_grid=None,
                host_label="the host"):
    """The views of the spare-solar chart. member_use[n, H] and shares[n] include the host first (id 'host').
    host_label is the host's short name with its article, as used in a sentence, e.g. "the Institut"."""
    owner = host_label[4:] if host_label.lower().startswith("the ") else host_label     # "Institut" for the toggle
    gen, host_use = np.asarray(gen, float), np.asarray(host_use, float)
    dates, hours, _, _ = local_parts(times)
    year = int(np.asarray(times, dtype="datetime64[Y]")[0].astype(int) + 1970)
    days = day_labels(year)
    hourly = {"total": np.maximum(gen - host_use, 0.0)}
    labels = {"total": "Total spare", "host_share": f"{owner}'s {{share}} share", "cep9_grid": "To the grid, CEP9 split",
              "our_tool_grid": "To the grid, our tool"}
    what = {"total": f"solar minus {host_label}'s own use",
            "host_share": f"the part of {host_label}'s own share it can't use (share x solar minus its use, where above 0)",
            "cep9_grid": "for each hour, the sum over all members of what they can't use of their share (share x solar minus use, where above 0)",
            "our_tool_grid": "what our tool's battery agent sends to the grid (no battery), every hour"}
    if shares is not None and member_use is not None:
        shares = np.asarray(shares, float)
        member_use = np.atleast_2d(np.asarray(member_use, float))
        hourly["host_share"] = np.maximum(shares[0] * gen - host_use, 0.0)
        hourly["cep9_grid"] = np.maximum(shares[:, None] * gen[None, :] - member_use, 0.0).sum(0)
        labels["host_share"] = labels["host_share"].format(share=f"{shares[0]:.0%}")
    if our_tool_grid is not None:
        hourly["our_tool_grid"] = np.asarray(our_tool_grid, float)
    views = {}
    for key, series in hourly.items():
        g = to_grid(dates, hours, series, year)
        cs = closed_shares(g, days)
        views[key] = {"label": labels[key], "what": what[key], "total_kwh": round(float(series.sum())),
                      "share_of_solar": round(float(series.sum() / gen.sum()), 4) if gen.sum() else 0.0,
                      "closed_shares": cs, "sentence": sentence(key, series.sum(), gen.sum(), cs, host_label),
                      "grid": [[round(float(v), 2) for v in row] for row in g]}
    return {"year": year, "days": days, "views": views, "colour_kwh": list(COLOUR_KWH),
            "holidays": [{"name": n, "from": a.isoformat(), "to": b.isoformat()} for n, a, b in HOLIDAYS.get(year, [])],
            "holiday_source": "Christmas and Easter: Catalan school calendars 2022-23 (Ordre EDU/113/2022) and 2023-24; "
                              "July-August: Breno's choice. The demand model closes the Institut in July-August, "
                              "23 Dec-7 Jan and at Easter (Monday of Holy Week to Easter Monday).",
            "time_note": "Local time in Barcelona (Europe/Madrid, with summer time). Each row is one clock hour, "
                         "e.g. 13:00 = 13:00-14:00."}


def sentence(key, total, solar, cs, host_label):
    share = f"{total / solar:.1%} of the solar" if solar else "nothing"
    head = {"total": f"{total:,.0f} kWh a year is spare ({share})",
            "host_share": f"{host_label} can't use {total:,.0f} kWh a year of its own share ({share})",
            "cep9_grid": f"Under CEP9's fixed split {total:,.0f} kWh a year goes to the grid ({share})",
            "our_tool_grid": f"With our tool {total:,.0f} kWh a year goes to the grid ({share})"}[key]
    if total <= 0:
        return head + "."
    return (f"{head}. {cs['closed']:.0%} of it falls on weekends ({cs['weekend']:.0%}) and on school-holiday "
            f"weekdays ({cs['holiday_weekdays']:.0%}), when {host_label} is closed.")


def season_profiles(times, series):
    """Mean day (local hours 0-23) per season and day type: {season: {weekday: [24], weekend: [24]}}."""
    _, hours, wdays, months = local_parts(times)
    series = np.asarray(series, float)
    out = {}
    for name, months_in in SEASONS.items():
        m = np.isin(months, months_in)
        out[name] = {}
        for label, mask in (("weekday", wdays < 5), ("weekend", wdays >= 5)):
            out[name][label] = [round(float(series[m & mask & (hours == h)].mean()), 3) for h in range(24)]
    return out
