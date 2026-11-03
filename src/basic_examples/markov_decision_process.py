
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.constants import EXAMPLE_SEED
from src.utils.enums import StudentState, MentorActions

# simulate 100 students over 12 months with a simple Markov decision process model for dropout behavior

import numpy as np

rng = np.random.default_rng(EXAMPLE_SEED)  # set a random seed for reproducibility


class Student:
    def __init__(self, id):
        self.id = id
        self.state = StudentState.ACTIVE if rng.random() < 0.8 else StudentState.AT_RISK  # 80% start as ACTIVE, 20% as AT_RISK

    def step(self, mentor_action, transition_matrix):
        next_state_probabilities = transition_matrix[mentor_action]
        self.state = StudentState(rng.choice(len(next_state_probabilities), p=next_state_probabilities))

class School:
    def __init__(self):
        # transition probabilities for each state given mentor actions
        self.probabilities = {
            StudentState.ACTIVE: {
                MentorActions.PROVIDE_SUPPORT: [0.9, 0.1, 0.0],  # P(ACTIVE|SUPPORT), P(AT_RISK|SUPPORT), P(DROPPED_OUT|SUPPORT)
                MentorActions.IGNORE: [0.7, 0.2, 0.1],  # P(ACTIVE|IGNORE), P(AT_RISK|IGNORE), P(DROPPED_OUT|IGNORE)
            },
            StudentState.AT_RISK: {
                MentorActions.PROVIDE_SUPPORT: [0.6, 0.3, 0.1],  # P(ACTIVE|SUPPORT), P(AT_RISK|SUPPORT), P(DROPPED_OUT|SUPPORT)
                MentorActions.IGNORE: [0.4, 0.4, 0.2],  # P(ACTIVE|IGNORE), P(AT_RISK|IGNORE), P(DROPPED_OUT|IGNORE)
            },
            StudentState.DROPPED_OUT: {
                MentorActions.PROVIDE_SUPPORT: [0.0, 0.0, 1.0],  # P(ACTIVE|SUPPORT), P(AT_RISK|SUPPORT), P(DROPPED_OUT|SUPPORT)
                MentorActions.IGNORE: [0.0, 0.0, 1.0],  # P(ACTIVE|IGNORE), P(AT_RISK|IGNORE), P(DROPPED_OUT|IGNORE)
            }
        }

        # reward for arriving in a state (e.g., ACTIVE is good, DROPPED_OUT is bad)
        self.rewards = {
            StudentState.ACTIVE: 10,
            StudentState.AT_RISK: 0,
            StudentState.DROPPED_OUT: -20
        }

        # cost for taking an action (e.g., providing support has a cost)
        self.costs = {
            MentorActions.PROVIDE_SUPPORT: 3,
            MentorActions.IGNORE: 0
        }
        # discount factor for future reward-
        self.discount_factor = 0.9

        # initialize students and their values
        self.students = [Student(id=i) for i in range(100)]
        # initialize values for each state
        self.values = {state: 0 for state in StudentState}
        # results
        self.results = {}

    def get_values_iteration(self, num_iterations=1000, tolerance=1e-8):
        for iteration in range(num_iterations):
            new_values = {}
            for state in StudentState:
                if state == StudentState.DROPPED_OUT:
                    # probability * (reward + discounted future value)
                    new_values[state] = self.rewards[state] + self.discount_factor * self.values[state]  # terminal state, no future value
                    continue

                action_values = []
                for action in MentorActions:
                    next_state_probs = self.probabilities[state][action]
                    expected_value = 0
                    for i, prob in enumerate(next_state_probs):
                        next_state = StudentState(i)
                        expected_value += prob * self.values[next_state]
                    action_value = self.rewards[state] - self.costs[action] + self.discount_factor * expected_value
                    action_values.append(action_value)
                new_values[state] = max(action_values)
            delta = max(abs(new_values[state] - self.values[state]) for state in StudentState)
            self.values = new_values
            if delta < tolerance:
                break

    def step(self, student):
        # Simulate a student's transition based on their current state and the action based on value iteration
        current_state = student.state
        if current_state == StudentState.DROPPED_OUT:
            return

        # choose the best action based on the current values
        best_action = None
        best_value = float('-inf')
        for action in MentorActions:
            next_state_probs = self.probabilities[current_state][action]
            expected_value = 0
            for i, prob in enumerate(next_state_probs):
                next_state = StudentState(i)
                expected_value += prob * self.values[next_state]
            action_value = self.rewards[current_state] - self.costs[action] + self.discount_factor * expected_value
            if action_value > best_value:
                best_value = action_value
                best_action = action
        # transition the student to the next state based on the best action
        student.step(best_action, self.probabilities[current_state])

    def simulate(self, num_students, num_steps):
        self.students = [Student(id=i) for i in range(num_students)]
        self.results = {}
        for month in range(1, num_steps + 1):
            for student in self.students:
                self.step(student)
            self.results[month] = self.count_states()

    def count_states(self):
        state_counts = {state: 0 for state in StudentState}
        for student in self.students:
            state_counts[student.state] += 1
        return state_counts

    def run(self, num_students=100, num_steps=12):
        self.get_values_iteration()
        self.simulate(num_students, num_steps)
        return self.results


def main():
    school = School()
    print(school.run(num_students=100, num_steps=12)[12])


if __name__ == "__main__":
    main()
