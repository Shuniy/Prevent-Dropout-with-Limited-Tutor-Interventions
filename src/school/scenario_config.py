"""Versioned scenario inputs using the repository's TOML convention."""

from dataclasses import dataclass
from pathlib import Path
import math
import tomllib


@dataclass(frozen=True)
class ScenarioConfig:
    version: str = "cmdp_v1"
    num_students: int = 100
    num_mentors: int = 2
    horizon: int = 12
    monthly_admissions: int = 10
    monthly_appointments: int = 50
    appointments_per_programme: int = 5
    cost_per_appointment: float = 1.0
    budget: float = 150.0
    seed: int = 42
    effect_strength: float = 1.0
    max_programmes_per_student: int = 1
    fairness_window: int = 4
    fairness_min_access: float = 0.2
    fairness_enabled: bool = True
    fairness_grouping_attribute: str = "disadvantage_proxy"
    fairness_allow_shortfall: bool = True
    fairness_metric: str = "minimum_access_coverage"
    fairness_need_stratification: str = "frozen_condition"
    fairness_small_group_threshold: int = 30
    planner_time_limit: float = 10.0
    planner_failure_mode: str = "raise"

    def __post_init__(self):
        for name in (
            "num_students",
            "num_mentors",
            "monthly_admissions",
            "monthly_appointments",
            "seed",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in ("horizon", "fairness_window"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("budget", "cost_per_appointment"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        for name in ("effect_strength", "fairness_min_access"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be within [0, 1]")
        if self.appointments_per_programme != 5:
            raise ValueError("version 1 requires five appointments per monthly programme")
        if self.max_programmes_per_student != 1:
            raise ValueError(
                "version 1 supports one programme per student; repeats require a future model"
            )
        if not math.isfinite(self.planner_time_limit) or self.planner_time_limit <= 0:
            raise ValueError("planner_time_limit must be positive and finite")
        if self.planner_failure_mode not in ("raise", "wait"):
            raise ValueError("planner_failure_mode must be raise or wait")
        if self.fairness_grouping_attribute not in ("disadvantage_proxy", "sex_source"):
            raise ValueError("fairness grouping must select one authorized audit attribute")
        if self.fairness_metric != "minimum_access_coverage":
            raise ValueError("unsupported fairness metric")
        if self.fairness_need_stratification != "frozen_condition":
            raise ValueError("unsupported fairness need stratification")
        if type(self.fairness_enabled) is not bool or type(self.fairness_allow_shortfall) is not bool:
            raise ValueError("fairness mode flags must be boolean")
        if type(self.fairness_small_group_threshold) is not int or self.fairness_small_group_threshold < 1:
            raise ValueError("small group threshold must be a positive integer")

    @classmethod
    def load(cls, path: str | Path):
        with Path(path).open("rb") as source:
            data = tomllib.load(source)
        fields = {"enabled": "fairness_enabled", "metric": "fairness_metric",
                  "assessment_window_months": "fairness_window",
                  "grouping_attribute": "fairness_grouping_attribute",
                  "need_stratification": "fairness_need_stratification",
                  "target_coverage": "fairness_min_access",
                  "allow_shortfall": "fairness_allow_shortfall",
                  "small_group_threshold": "fairness_small_group_threshold"}
        fairness = data.get("fairness", {})
        unknown = set(fairness) - fields.keys()
        if unknown:
            raise ValueError(f"unsupported fairness settings: {sorted(unknown)}")
        values = dict(data["cmdp"])
        for key, value in fairness.items():
            if fields[key] in values:
                raise ValueError(f"duplicate fairness setting: {key}")
            values[fields[key]] = value
        return cls(**values)
