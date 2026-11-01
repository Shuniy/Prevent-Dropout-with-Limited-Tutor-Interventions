"""Run the initial constrained school simulation environment."""

try:
    from .models.school import School
except ImportError:  # Support running ``python src/main.py`` directly.
    from models.school import School


class SchoolCMDPEnvironment:
    """Track school-wide CMDP progress around the current assignment model.

    The school state advances one month at a time. For now, the action is the
    existing random feasible student-mentor assignment, the constraint is the
    available budget, and the score stays at zero until scoring is added.
    """

    def __init__(self, school: School) -> None:
        self.school = school
        self.current_month = 0
        self.score = 0.0
        self.progress: list[dict[str, object]] = []

    def step(self) -> dict[str, object]:
        """Advance the school by one month and record its CMDP state."""

        if self.current_month >= self.school.num_months:
            raise RuntimeError("the school simulation is already complete")

        self.current_month += 1

        # Step: 3 - Student-mentor assignment and scheduled intervention.
        new_assignments = self.school.step(self.current_month)

        # Step: 4 - Initial CMDP progress and score calculation.
        # Student outcome scoring will be added after activity and intervention
        # effects are defined, so the initial score intentionally remains zero.
        state: dict[str, object] = {
            "month": self.current_month,
            "progress": self.current_month / self.school.num_months,
            "student_mentor_assignments": dict(
                self.school.monthly_assignments[self.current_month]
            ),
            "assigned_students": len(new_assignments),
            "scheduled_sessions": sum(
                assignment.sessions for assignment in new_assignments
            ),
            "spent_budget": self.school.spent_budget,
            "remaining_budget": self.school.remaining_budget,
            "score": self.score,
        }
        self.progress.append(state)
        return state

    def run(self) -> list[dict[str, object]]:
        """Run every remaining month and return the recorded CMDP states."""

        while self.current_month < self.school.num_months:
            self.step()
        return list(self.progress)


def main() -> None:
    # Step: 1 - School simulation initialisation.
    school = School()

    # Step: 2 - CMDP simulation run for the configured school months.
    environment = SchoolCMDPEnvironment(school)
    progress = environment.run()

    final_state = progress[-1]
    print(
        "School CMDP simulation complete: "
        f"months={final_state['month']}, "
        f"spent_budget={final_state['spent_budget']}, "
        f"score={final_state['score']}"
    )


if __name__ == "__main__":
    main()
