"""Lazy import aliases for pre-numbering serialized baseline estimators.

Do not rewrite or retrain artifacts merely because source directories move.
Only old baseline-class module names are aliased; new code uses numbered paths.
"""
import importlib
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader
import sys

ALIASES = {
    'pipeline.demand_baseline_hour_of_week': 'pipeline.step_05_demand_baseline_hour_of_week',
    'pipeline.demand_baseline_hour_of_week.model': 'pipeline.step_05_demand_baseline_hour_of_week.model',
    'pipeline.demand_baseline_seasonal': 'pipeline.step_05_demand_baseline_seasonal',
    'pipeline.demand_baseline_seasonal.model': 'pipeline.step_05_demand_baseline_seasonal.model',
}


class AliasLoader(Loader):
    def __init__(self, target):
        self.target = target

    def create_module(self, spec):
        return importlib.import_module(self.target)

    def exec_module(self, module):
        pass


class ArtifactAliasFinder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ALIASES:
            return spec_from_loader(fullname, AliasLoader(ALIASES[fullname]),
                                    is_package=not fullname.endswith('.model'))
        return None


def install():
    if not any(isinstance(item, ArtifactAliasFinder) for item in sys.meta_path):
        sys.meta_path.append(ArtifactAliasFinder())
