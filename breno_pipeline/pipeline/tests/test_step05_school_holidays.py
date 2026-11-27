"""Step 05 school holidays in the rule-based demand shape (offline)."""
import numpy as np

from step05_forecast_demand import baseline_profiles as dm


def test_easter_sunday_known_years():
    assert str(dm.easter_sunday(2023)) == "2023-04-09"
    assert str(dm.easter_sunday(2024)) == "2024-03-31"
    assert str(dm.easter_sunday(2025)) == "2025-04-20"


def test_easter_holidays_match_the_2023_school_calendar():
    days = np.arange(np.datetime64("2023-03-30"), np.datetime64("2023-04-14"))
    hol = dm.easter_holidays(days)
    closed = [str(d) for d, h in zip(days, hol) if h]
    assert closed[0] == "2023-04-03" and closed[-1] == "2023-04-10" and len(closed) == 8   # Ordre EDU/113/2022


def test_school_shape_is_closed_at_easter():
    times = np.arange(np.datetime64("2023-01-01T00:30"), np.datetime64("2024-01-01T00:30"), np.timedelta64(1, "h"))
    school = dm.profile_shapes(times, profile_path="no/such/file.json")["school"]
    at = lambda s: school[np.where(times == np.datetime64(s))[0][0]]
    # Wednesday 11:00 UTC (13:00 local): open on 29 March, closed in Easter week (5 April)
    assert at("2023-04-05T11:30") < 0.2 * at("2023-03-29T11:30")
    assert at("2023-04-12T11:30") == at("2023-03-29T11:30")        # open again the week after
