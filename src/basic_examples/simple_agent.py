
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.constants import EXAMPLE_SEED

import numpy as np
rng = np.random.default_rng(EXAMPLE_SEED)  # set a random seed for reproducibility
# Simple agent-based model to simulate student dropout based on motivation

class Student:
    def __init__(self, motivation):
        self.motivation = motivation
        self.is_dropout = False

    def step(self):
        if self.is_dropout:
            return

        self.motivation += rng.uniform(-0.1, 0.1)  # motivation decreases over time
        self.motivation = max(0, min(1, self.motivation))  # keep motivation in [0, 1]

        # lower motivation increases dropout probability
        dropout_probability = (1 - self.motivation) * 0.1
        if rng.random() < dropout_probability:
            self.is_dropout = True

def main():
    students = [Student(rng.uniform(0.5, 1.0)) for _ in range(100)]  # initialize students with random motivation
    # simulate 12 months
    for month in range(1, 13):
        for student in students:
            student.step()

        num_dropouts = sum(student.is_dropout for student in students)

    print(f"Dropped out: {num_dropouts}")


if __name__ == "__main__":
    main()
