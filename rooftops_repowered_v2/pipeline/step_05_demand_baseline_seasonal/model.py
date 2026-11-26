from pipeline.step_05_demand_baseline_hour_of_week.model import GroupMeanBaseline


class SeasonalBaseline(GroupMeanBaseline):
    def __init__(self):
        super().__init__('seasonal')
