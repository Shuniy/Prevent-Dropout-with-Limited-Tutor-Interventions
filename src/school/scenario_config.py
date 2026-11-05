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

    @classmethod
    def load(cls, path: str | Path):
        with Path(path).open("rb") as source:
            return cls(**tomllib.load(source)["cmdp"])
