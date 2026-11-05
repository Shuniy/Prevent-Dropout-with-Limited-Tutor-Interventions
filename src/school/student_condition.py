"""Conditions are simulated assumptions, never observed dropout labels."""

from enum import Enum


class StudentCondition(str, Enum):
    STABLE = "stable"
    VULNERABLE = "vulnerable"
    DISENGAGED = "disengaged"
    WITHDRAWN = "withdrawn"


STATES = tuple(StudentCondition)
