"""Step 03 helper: scale a layout's hourly output to the real number of panels.

    python -m step03_simulate_generation.scale_panels --yield data\\pv\\cep9_institut_yield.json ^
        --hourly data\\pv\\cep9_institut_hourly.csv --panels 108 --out data\\pv\\cep9_institut_108

Why: CEP9's real plant is 108 x 540 W = 58.32 kWp on the Institut, laid out East-West ("Delta Wing",
10 degrees, back to back, no gaps between rows) [CEP9, email from César Ochoa, 27 Nov 2026]. Our step 02
layout only makes south-facing rows with shade gaps, so only 97 panels fit. Until step 02/03 has an
East-West option, the 97-panel hourly output is multiplied by 108 / 97.

ASSUMPTION: every extra panel makes as much as the average modelled panel, every hour. (A real East-West
plant makes a flatter day curve, more in the morning and evening and less at noon; that is not modelled.)

Writes <out>_hourly.csv (same columns as step 03) and <out>_yield.json (a copy of the yield file with the
panels, kWp, yearly and monthly kWh and peak scaled, and a "scaled" block saying how).
The panel drawing (panel_list) stays the 97 panels our layout fits.
"""
import argparse
import csv
import json
from pathlib import Path


def scale_yield(y, panels):
    """Yield dict from step 03 -> a scaled copy. factor = panels / modelled panels."""
    yl = y["yield"]
    factor = panels / yl["panels"]
    out = {**y, "yield": dict(yl)}
    s = out["yield"]
    s["panels"] = panels
    s["kwp"] = round(panels * yl["panel_wp"] / 1000, 2)
    s["yearly_kwh"] = round(yl["yearly_kwh"] * factor)
    s["monthly_kwh"] = [round(m * factor) for m in yl["monthly_kwh"]]
    if yl.get("peak_hour_kw") is not None:
        s["peak_hour_kw"] = round(yl["peak_hour_kw"] * factor, 2)
    out["scaled"] = {"from_panels": yl["panels"], "to_panels": panels, "factor": round(factor, 6),
                     "from_yearly_kwh": yl["yearly_kwh"],
                     "assumption": "ASSUMPTION: the extra panels make as much as the average modelled panel, every hour",
                     "why": "the real plant is East-West ('Delta Wing', 10 deg, back to back); our layout only fits "
                            f"{yl['panels']} south-facing panels [CEP9, email from César Ochoa, 27 Nov 2026]"}
    out.pop("variants", None)        # the layout options were for the modelled panels, not the scaled plant
    return out, factor


def main():
    ap = argparse.ArgumentParser(description="Scale a step 03 hourly output to the real panel count")
    ap.add_argument("--yield", dest="yield_json", required=True, help="step 03 <name>_yield.json")
    ap.add_argument("--hourly", required=True, help="step 03 <name>_hourly.csv (time_utc, kwh)")
    ap.add_argument("--panels", type=int, required=True, help="the real number of panels")
    ap.add_argument("--out", required=True, help="output name, without extension")
    args = ap.parse_args()
    y = json.loads(Path(args.yield_json).read_text(encoding="utf-8"))
    scaled, factor = scale_yield(y, args.panels)
    with open(args.hourly, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(f"{out}_hourly.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_utc", "kwh"])
        for r in rows:
            w.writerow([r["time_utc"], round(float(r["kwh"]) * factor, 4)])
    Path(f"{out}_yield.json").write_text(json.dumps(scaled, indent=2, ensure_ascii=False), encoding="utf-8")
    yl = scaled["yield"]
    print(f"{y['yield']['panels']} -> {yl['panels']} panels (x {factor:.4f}): {yl['kwp']} kWp, "
          f"{yl['yearly_kwh']:,} kWh a year, {round(yl['yearly_kwh'] / yl['kwp'])} kWh per kWp")
    print(f"-> {out}_hourly.csv, {out}_yield.json")


if __name__ == "__main__":
    main()
