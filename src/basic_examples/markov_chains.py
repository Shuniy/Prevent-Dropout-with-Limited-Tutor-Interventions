# simulating simple markov chains with a transition matrix

from enum import Enum
import numpy as np

rng = np.random.default_rng(5726455)  # set a random seed for reproducibility

class StudentState(Enum):
    ACTIVE = 0
    AT_RISK = 1
    DROPPED_OUT = 2

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
            state_counts = self.count_states()
            print(f"Step {step + 1}: {state_counts[StudentState.ACTIVE]} active, "
                  f"{state_counts[StudentState.AT_RISK]} at risk, "
                  f"{state_counts[StudentState.DROPPED_OUT]} dropped out.")

school = School(num_students=100, transition_matrix=[[0.8, 0.15, 0.05], [0.1, 0.7, 0.2], [0.0, 0.0, 1.0]])
school.simulate(num_steps=12)