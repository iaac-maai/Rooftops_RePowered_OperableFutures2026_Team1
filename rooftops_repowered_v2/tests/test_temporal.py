import pandas as pd
import pytest

from pipeline.common import InputError
from pipeline.temporal import as_utc, standard_wall_time
from pipeline.step_03_pvgis.importer import import_hourly


def test_fall_dst_repeated_civil_hour_preserves_two_utc_intervals():
    local = pd.Series(['2026-10-25T02:00:00+02:00', '2026-10-25T02:00:00+01:00'])
    utc = as_utc(local)
    assert utc.diff().dropna().iloc[0] == pd.Timedelta(hours=1)
    assert not utc.duplicated().any()


def test_naive_times_rejected_and_source_standard_calendar_ignores_dst():
    with pytest.raises(InputError):
        as_utc(pd.Series(['2026-10-25T02:00:00']))
    values = standard_wall_time(pd.Series(['2026-07-01T12:00:00Z']), 'Europe/Madrid')
    assert values.iloc[0].hour == 13  # civil time would be 14:00


def test_pvgis_power_conversion_and_minute_offsets_preserved(tmp_path):
    source = tmp_path / 'pvgis.csv'
    source.write_text('Latitude: 41\ntime,P,T2m\n20260101:0010,1000,12\n20260101:0110,500,13\n\nFooter\n')
    result = import_hourly(source, 'UTC', 'W')
    assert result.pv_generation_kwh.tolist() == [1, 0.5]
    assert result.timestamp_utc.dt.minute.tolist() == [10, 10]
    with pytest.raises(InputError):
        import_hourly(source, 'Europe/Madrid')
