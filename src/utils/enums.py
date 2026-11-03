"""Shared categorical types for models and simulation examples."""

from enum import Enum, IntEnum
from typing import Literal


class StudentState(Enum):
    ACTIVE = 0
    AT_RISK = 1
    DROPPED_OUT = 2


class MentorActions(Enum):
    PROVIDE_SUPPORT = 0
    IGNORE = 1


class CMDPStudentState(IntEnum):
    ACTIVE = 0
    AT_RISK = 1
    DROPPED_OUT = 2


class CMDPMentorActions(IntEnum):
    PROVIDE_SUPPORT = 0
    IGNORE = 1


SupportType = Literal[
    "attendance_planning",
    "device_access",
    "family_finances",
    "family_liaison",
    "homework_support",
    "language_support",
    "learning_access",
    "peer_support",
    "reentry_support",
    "school_meals",
    "transport_assessment",
    "tutoring",
    "wellbeing_checkin",
]
