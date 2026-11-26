from io import StringIO
import pandas as pd
import numpy as np

from pipeline.common import InputError
from pipeline.temporal import require_hourly_index


def validate_generation_role(settings):
    """Do not silently promote a rooftop validation scenario into shared energy."""
    if settings.get('generation_role') in ('counterfactual_validation_only', 'existing_unverified'):
        raise InputError('This rooftop record cannot supply case-study generation: retrospective potential is counterfactual and existing PV needs verified installation specifications.')
    if settings.get('energy_sharing_eligible') is False:
        raise InputError('This provisional rooftop record is not cleared for case-study energy accounting. Verify capacity/design and document a separate approved generation record first.')


def validate_case_study_supply(frame):
    """Reject explicitly hypothetical/ineligible series even if manually repointed."""
    if 'hypothetical' in frame and frame.hypothetical.astype(str).str.lower().eq('true').any():
        raise InputError('Hypothetical PVGIS sensitivity cannot supply verified case-study energy sharing.')
    if 'energy_sharing_eligible' in frame and not frame.energy_sharing_eligible.astype(str).str.lower().eq('true').all():
        raise InputError('PV series is explicitly ineligible or unverified for case-study energy sharing.')
    if 'generation_role' in frame and frame.generation_role.isin(['counterfactual_validation_only','existing_unverified']).any():
        raise InputError('Counterfactual/unverified generation cannot be used as existing case-study supply.')


def import_hourly(path, timestamp_basis, power_unit='W', interval_hours=1.0):
    """Read a PVGIS seriescalc export (time,P); never infer a host or capacity.

    PVGIS simulation/configuration, including kWp, is external and must be recorded
    by the caller. P represents average power; conversion to hourly energy is an
    explicit one-hour approximation. Preserve source timestamps, including minute
    offsets; rounding/realignment needs a later documented choice.
    """
    if timestamp_basis != 'UTC' or power_unit not in ('W', 'kW') or interval_hours != 1:
        raise InputError('Import requires explicit UTC timestamps, W/kW power and a one-hour interval.')
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith('time,') and 'P' in line.split(',')), None)
    if start is None:
        raise InputError('Expected a PVGIS hourly CSV header time,P,...; other schemas need an explicit adapter.')
    data_lines = []
    for line in lines[start + 1:]:
        if not line[:8].isdigit() or ':' not in line[:14]:
            break
        data_lines.append(line)
    if not data_lines:
        raise InputError('No PVGIS hourly records found.')
    data = pd.read_csv(StringIO('\n'.join([lines[start], *data_lines])))
    times = pd.to_datetime(data.time, format='%Y%m%d:%H%M', utc=True, errors='raise')
    require_hourly_index(times, 'PVGIS')
    power = pd.to_numeric(data.P, errors='raise')
    if not np.isfinite(power).all() or power.lt(0).any():
        raise InputError('PVGIS power must be finite and nonnegative.')
    result = pd.DataFrame({'timestamp_utc': times,
                           'pv_generation_kwh': power / (1000 if power_unit == 'W' else 1),
                           'data_origin': 'SIMULATED_PHYSICS'})
    return result
