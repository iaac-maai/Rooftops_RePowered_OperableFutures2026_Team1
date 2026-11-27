"""Read costs.csv: one row per cost, with its low and high value, source and status.

Columns (keep these names: other team members edit the file): key, value, unit, low, high, source, status.
status is "sourced" (the source column says where the number comes from, full links in docs/SOURCES.md)
or "ASSUMPTION" (a value we chose; the source column says why, or is empty).
"""
import csv
from pathlib import Path

COSTS_CSV = Path(__file__).resolve().parent / "costs.csv"
COLUMNS = ("key", "value", "unit", "low", "high", "source", "status")
STATUSES = ("sourced", "ASSUMPTION")


def _num(text):
    text = (text or "").strip()
    return float(text) if text else None


def load_costs(path=COSTS_CSV):
    """costs.csv -> {key: {"value", "unit", "low", "high", "source", "status"}} (numbers as floats, blanks as None)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"{path} is missing the column(s) {', '.join(sorted(missing))}")
        rows = {}
        for r in reader:
            if not (r.get("key") or "").strip():
                continue
            rows[r["key"].strip()] = {"value": _num(r["value"]), "unit": r["unit"].strip(), "low": _num(r["low"]),
                                      "high": _num(r["high"]), "source": (r["source"] or "").strip(),
                                      "status": (r["status"] or "").strip()}
    return rows


def values(costs):
    """{key: central value} from load_costs()."""
    return {k: r["value"] for k, r in costs.items()}


def value(key, path=COSTS_CSV):
    """One central value, e.g. value("battery_installed_eur_per_kwh")."""
    costs = load_costs(path)
    if key not in costs:
        raise SystemExit(f"{key} is not in {path}")
    return costs[key]["value"]
