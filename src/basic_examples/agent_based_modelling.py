
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.constants import DEFAULT_RNG as rng



# Agent based model to simulate student dropout based on motivation and external factors. A more realistic ABM would introduce relationships between students, teacher interventions, household circumstances, and feedback effects.
class Student:
    def __init__(self, motivation, external_factor):
        self.motivation = motivation
        self.external_factor = external_factor
        self.is_dropout = False

    def step(self):
        if self.is_dropout:
            return

        # motivation decreases over time and is influenced by external factors
        self.motivation += rng.uniform(-0.1, 0.1) + self.external_factor * 0.05
        self.motivation = max(0, min(1, self.motivation))  # keep motivation in [0, 1]

        # lower motivation increases dropout probability
        dropout_probability = (1 - self.motivation) * 0.1
        if rng.random() < dropout_probability:
            self.is_dropout = True

class School:
    def __init__(self, num_students):
        self.students = [Student(rng.uniform(0.5, 1.0), rng.uniform(-0.1, 0.1)) for _ in range(num_students)]

    def step(self):
        # lets say there are some external factors that affect all students, like a new policy or a change in the school environment
        external_factor = rng.uniform(-0.1, 0.1)
        for student in self.students:
            student.external_factor = external_factor
            student.step()

    def get_dropout_count(self):
        return sum(student.is_dropout for student in self.students)

    def simulate(self, months):
        for month in range(months):
            self.step()
        return self.get_dropout_count()


def main():
    school = School(num_students=100)
    print(f"Dropped out: {school.simulate(months=12)}")


if __name__ == "__main__":
    main()
