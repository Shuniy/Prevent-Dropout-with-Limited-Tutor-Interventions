
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.constants import EXAMPLE_SEED
from src.utils.enums import StudentState

# simulating simple markov chains with a transition matrix

import numpy as np

rng = np.random.default_rng(EXAMPLE_SEED)  # set a random seed for reproducibility


class Student:
    def __init__(self, transition_matrix):
        self.transition_matrix = transition_matrix
        self.state = StudentState.ACTIVE

    def step(self):
        current_state_index = self.state.value
        next_state_probabilities = self.transition_matrix[current_state_index]
        self.state = StudentState(rng.choice(len(next_state_probabilities), p=next_state_probabilities))

class School:
    def __init__(self, num_students, transition_matrix):
        self.students = [Student(transition_matrix) for _ in range(num_students)]

    def step(self):
        for student in self.students:
            student.step()

    def count_states(self):
        state_counts = {state: 0 for state in StudentState}
        for student in self.students:
            state_counts[student.state] += 1
        return state_counts

    def simulate(self, num_steps):
        for step in range(num_steps):
            self.step()
        return self.count_states()


def main():
    school = School(num_students=100, transition_matrix=[[0.8, 0.15, 0.05], [0.1, 0.7, 0.2], [0.0, 0.0, 1.0]])
    print(school.simulate(num_steps=12))


if __name__ == "__main__":
    main()
