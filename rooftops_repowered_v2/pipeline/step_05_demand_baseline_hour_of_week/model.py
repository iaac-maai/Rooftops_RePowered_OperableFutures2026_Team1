import numpy as np
import pandas as pd


class GroupMeanBaseline:
    """Training-only intensity means; no historical meter required at inference."""

    def __init__(self, grouping='hour_of_week'):
        self.grouping = grouping

    def _keys(self, frame):
        times = pd.to_datetime(frame.timestamp_local_standard)
        period = times.dt.day_of_week * 24 + times.dt.hour if self.grouping == 'hour_of_week' else (times.dt.month % 12) // 3
        return pd.DataFrame({'building_use': frame.building_use.to_numpy(), 'period': period.to_numpy()})

    def fit(self, frame):
        keys = self._keys(frame)
        keys['target'] = frame.electricity_wh_m2.to_numpy()
        self.means_ = keys.groupby(['building_use', 'period']).target.mean()
        self.use_means_ = keys.groupby('building_use').target.mean()
        self.global_mean_ = float(keys.target.mean())
        return self

    def predict_intensity(self, frame):
        keys = self._keys(frame)
        values = self.means_.reindex(pd.MultiIndex.from_frame(keys)).to_numpy()
        fallback = keys.building_use.map(self.use_means_).fillna(self.global_mean_).to_numpy()
        return np.maximum(0, np.where(np.isnan(values), fallback, values))
