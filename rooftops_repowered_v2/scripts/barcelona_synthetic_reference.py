"""Create non-metered hourly shape scenarios from Barcelona sector aggregates."""
import argparse
import csv
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path


def generate(source, output, postal, year):
    values = {}
    excluded = {"Residencial": 0, "Serveis": 0}
    with source.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["Codi_Postal"].zfill(5) != postal or row["Sector_Economic"] not in excluded:
                continue
            if int(row["year"]) != year:
                continue
            day = date.fromisoformat(row["Data"])
            if day.year != year:
                raise ValueError("Year and date disagree")
            value = float(row["Valor"].replace(",", "."))
            if value < 0:
                raise ValueError("Negative consumption")
            match = re.search(r"(\d{2}):\d{2}", row["Tram_Horari"])
            if not match:
                excluded[row["Sector_Economic"]] += value
                continue
            hour = int(match.group(1))
            if hour not in (0, 6, 12, 18):
                raise ValueError("Unrecognized time band")
            key = (row["Sector_Economic"], day, hour)
            if key in values:
                raise ValueError("Duplicate sector/day/band")
            values[key] = value
    start, end = date(year, 1, 1), date(year + 1, 1, 1)
    days = [start + timedelta(days=i) for i in range((end-start).days)]
    output.mkdir(parents=True, exist_ok=True)
    with (output / "hourly_normalized_shapes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sector", "local_time_label", "annual_fraction", "evidence", "training_eligible", "energy_sharing_eligible"])
        for sector in excluded:
            total = sum(values.get((sector, d, h), 0) for d in days for h in (0, 6, 12, 18))
            if not total or any((sector, d, h) not in values for d in days for h in (0, 6, 12, 18)):
                raise ValueError(f"Incomplete year for {sector}")
            for d in days:
                for hour in range(24):
                    fraction = values[(sector, d, (hour // 6) * 6)] / (6 * total)
                    label = datetime(d.year, d.month, d.day, hour).isoformat()
                    w.writerow([sector, label, f"{fraction:.14g}", "SYNTHETIC_UNIFORM_WITHIN_SIX_HOUR_BAND", "false", "false"])
    meta = {"source_file": source.name, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "postal_code_assumption": postal, "year": year, "excluded_no_consta_source_values": excluded,
            "source_unit": "unverified; normalized ratios only", "timestamp": "nominal local hour; DST and interval basis unverified",
            "method": "Each six-hour postal-sector total split evenly across six nominal hours and normalized over the year.",
            "limits": "Aggregate sector, not an individual building; no within-band hourly evidence, kWh magnitude, weather alignment, meter, AI label or sharing input.",
            "training_eligible": False, "energy_sharing_eligible": False}
    (output / "provenance.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path, default=Path("datasets/synthetic/barcelona_sector_reference"))
    p.add_argument("--postal", default="08018")
    p.add_argument("--year", type=int, default=2023)
    a = p.parse_args()
    generate(a.source, a.output, a.postal, a.year)
