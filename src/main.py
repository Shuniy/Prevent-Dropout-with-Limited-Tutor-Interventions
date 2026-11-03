"""Run feature-matched RAG interventions or the monthly allocation baseline."""

import argparse
from pathlib import Path

try:
    from .models.school import School
except ImportError:  # Support running ``python src/main.py`` directly.
    from models.school import School


class SchoolCMDPEnvironment:
    """Track school-wide CMDP progress around the current assignment model.

    The baseline advances monthly random feasible allocations with no outcome
    score. Intervention mode replays one programme per student and scores only
    appointment participation. This wrapper does not optimize a CMDP policy.
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

    def run_interventions(self, **kwargs) -> dict:
        """Run one RAG programme per student and record a participation score.

        This score is the fraction of the cohort's planned appointments recorded,
        not an intervention-effect, risk or school-retention estimate.
        """
        report = self.school.run_interventions(**kwargs)
        self.score = report["participation_completion_score"]
        self.current_month = self.school.num_months
        self.progress = [{**report["summary"], "score": self.score,
                          "score_definition": "recorded_sessions / cohort_planned_sessions"}]
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Allocate students and replay synthetic interventions with local Ollama.")
    parser.add_argument("--students", type=int, default=10)
    parser.add_argument("--mentors", type=int, default=2)
    parser.add_argument("--months", type=int, default=12, help="Allocation windows; students enter only once")
    parser.add_argument("--sessions", type=int, default=5, help="Total planned appointments per student")
    parser.add_argument("--capacity", type=int, default=10, help="Students per mentor per allocation window")
    parser.add_argument("--budget", type=float, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--history-root", type=Path)
    parser.add_argument("--output", type=Path, help="New or empty report directory")
    parser.add_argument("--allocation-only", action="store_true", help="Run the original monthly baseline without an LLM")
    args = parser.parse_args()
    school = School(num_students=args.students, num_mentors=args.mentors,
                    num_months=args.months, sessions_per_student=args.sessions,
                    students_per_mentor=args.capacity, budget=args.budget, seed=args.seed)
    environment = SchoolCMDPEnvironment(school)
    if args.allocation_only:
        final_state = environment.run()[-1]
        print(f"Allocation complete: months={final_state['month']}, spent_budget={final_state['spent_budget']}")
        return
    try:
        from .intervention.rag import OllamaClient
    except ImportError:
        from intervention.rag import OllamaClient
    options = {"output_dir": args.output, "client": OllamaClient(args.model),
               "progress": lambda message: print(message, flush=True)}
    if args.history_root is not None:
        options["root"] = args.history_root
    report = environment.run_interventions(**options)
    print(f"Intervention simulation {report['status']}: {report['summary']}")
    print(Path(report["output_dir"]) / "final_report.json")
    if report["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
