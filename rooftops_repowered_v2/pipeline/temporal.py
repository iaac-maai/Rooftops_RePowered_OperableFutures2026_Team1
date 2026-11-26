"""Explicit UTC for case-study accounting; preserve source time for training."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from pipeline.common import InputError


def as_utc(values):
    for value in values:
        if pd.isna(value) or pd.Timestamp(value).tzinfo is None:
            raise InputError('timestamp_utc requires an explicit UTC offset or Z; naive/missing times are not accepted.')
    return pd.to_datetime(values, utc=True)


def standard_wall_time(utc_values, timezone_name):
    """Training-compatible calendar: local standard time without DST.

    Reference sites and Barcelona are northern-hemisphere sites. January's offset
    supplies their winter standard time. Civil DST time is used separately for
    manual schedules. No historical meter year is silently joined to another year.
    """
    zone = ZoneInfo(timezone_name)
    utc = as_utc(utc_values)
    offsets = utc.map(lambda stamp: datetime(stamp.year, 1, 1, tzinfo=zone).utcoffset())
    return utc.dt.tz_localize(None) + pd.to_timedelta(offsets)


def require_hourly_index(index, label):
    values = pd.DatetimeIndex(index).sort_values()
    if values.has_duplicates:
        raise InputError(f'{label}: duplicate UTC hours.')
    if len(values) > 1 and not (values[1:] - values[:-1] == pd.Timedelta(hours=1)).all():
        raise InputError(f'{label}: timestamps must form continuous hourly intervals; no silent reindex/fill.')
