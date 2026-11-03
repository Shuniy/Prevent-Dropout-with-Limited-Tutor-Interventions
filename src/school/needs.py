"""Shared source/current support need rules; severity is not predicted risk."""


def calculate_needs(student) -> list[dict]:
    attendance = getattr(student, "initial_attendance_fraction_assumed", None)
    engagement = getattr(student, "initial_engagement_assumed", None)
    for name, value in (("attendance", attendance), ("engagement", engagement)):
        if value is not None and not 0 <= value <= 1:
            raise ValueError(f"initial {name} must be between 0 and 1")
    problems = []

    def add(problem: str, support_type: str, severity: float) -> None:
        problems.append({"problem": problem, "support_type": support_type,
                         "severity": round(severity, 4)})

    if getattr(student, "enrolled_initial_assumed", None) is False:
        add("return_to_learning", "reentry_support", 1.0)
    if student.learning_gap > 0 or student.past_failures_count > 0:
        add("learning_gap", "tutoring", max(student.learning_gap, min(1, student.past_failures_count / 4)))
    if attendance is not None and attendance < 0.85:
        add("attendance_routine", "attendance_planning", 1 - attendance)
    if student.no_home_internet:
        add("digital_access", "device_access", 0.5)
    if student.travel_over_30min:
        add("long_journey", "transport_assessment", (student.travel_time_category - 2) / 2)
    if student.study_time_category == 1:
        add("study_routine", "homework_support", 0.25)
    if student.family_relationship_rating <= 2:
        add("family_communication", "family_liaison", (3 - student.family_relationship_rating) / 3)
    if student.health_self_rating <= 2:
        add("wellbeing_checkin", "wellbeing_checkin", (3 - student.health_self_rating) / 3)
    if engagement is not None and engagement < 0.6:
        add("participation_opportunities", "peer_support", 1 - engagement)
    if getattr(student, "financial_need_verified", None) is True:
        add("verified_financial_need", "family_finances", 0.75)
    if not problems:
        add("routine_learning_checkin", "tutoring", 0.0)
    problems.sort(key=lambda problem: (-problem["severity"], problem["problem"]))
    return problems
